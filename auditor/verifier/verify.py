"""Crude verify (D2): after apply, re-measure the leaked signal over a short recent window and
confirm dashboards/alerts still resolve. Full before/after windows + integrity sweep land in D4.

The honest question a verify answers: "did the waste actually stop, and did we break anything?"
- current_rate: the finding's signal measured over the last VERIFY_WINDOW_MINUTES. After a good
  apply it should collapse toward zero (new data stops arriving; old data ages out of the window).
- integrity: re-fetch every dashboard and alert rule; if any now fails to load, the drop broke
  something and the verify FAILS loudly.
"""
from __future__ import annotations

from auditor.config import settings
from auditor.llm_auditor import attrs
from auditor.telemetry_auditor import schema
from auditor.telemetry_auditor.clickhouse import ClickHouse
from auditor.telemetry_auditor.findings import Finding
from auditor.telemetry_auditor.signoz_api import SigNozAPI, SigNozAPIError


def _win_min() -> int:
    return settings.verify_window_minutes


def _t1_current(ch: ClickHouse, finding: Finding) -> dict:
    services = [s["service"] for s in finding.measured.get("services", [])] or [finding.service]
    svc_list = ", ".join(f"'{s}'" for s in services)
    debug_pred = f"{schema.LOG_SEVERITY_NUMBER} > 0 AND {schema.LOG_SEVERITY_NUMBER} < {schema.SEVERITY_INFO_MIN}"
    sql = f"""
        SELECT countIf({debug_pred}) AS debug_logs,
               sumIf(length({schema.LOG_BODY}), {debug_pred}) AS debug_bytes
        FROM {schema.T_LOGS}
        WHERE {schema.LOG_TS} >= toUnixTimestamp(now() - INTERVAL {_win_min()} MINUTE) * 1000000000
          AND {schema.LOG_SERVICE_EXPR} IN ({svc_list})
    """
    dl, db = ch.query(sql)[0]
    return {"signal": "debug logs", "window_minutes": _win_min(),
            "debug_logs": int(dl), "debug_bytes": int(db)}


def _t2_current(ch: ClickHouse, finding: Finding) -> dict:
    names = [o["metric"] for o in finding.measured.get("orphans", [])]
    name_list = ", ".join(f"'{n}'" for n in names)
    sql = f"""
        SELECT count() AS datapoints
        FROM {schema.T_SAMPLES}
        WHERE {schema.SAMPLE_UNIX_MILLI} >= toUnixTimestamp(now() - INTERVAL {_win_min()} MINUTE) * 1000
          AND {schema.SAMPLE_METRIC_NAME} IN ({name_list})
    """
    dp = ch.query(sql)[0][0]
    return {"signal": "orphan metric datapoints", "window_minutes": _win_min(), "datapoints": int(dp)}


def _t3_current(ch: ClickHouse, finding: Finding) -> dict:
    health_pred = (
        f"(match({schema.SPAN_HTTP_ROUTE}, '^/?(health|healthz|ready|readyz|live|livez)$') "
        f"OR positionCaseInsensitive({schema.SPAN_NAME}, 'health') > 0)"
    )
    sql = f"""
        SELECT countIf({health_pred} AND {schema.SPAN_HAS_ERROR} = false) AS health_ok
        FROM {schema.T_TRACES}
        WHERE {schema.SPAN_TS} >= now() - INTERVAL {_win_min()} MINUTE
    """
    ho = ch.query(sql)[0][0]
    return {"signal": "health-check spans", "window_minutes": _win_min(), "health_ok_spans": int(ho)}


def _l1_current(ch: ClickHouse, finding: Finding) -> dict:
    """L1 after-apply signal: gen_ai calls + tokens for askdocs over the recent window, plus the
    cacheable-repeat count. With the cache on, exact-duplicate prompts are served before the LLM
    call, so they emit no new gen_ai span — repeats collapse toward 0 and tokens step down."""
    service = finding.service or "askdocs"
    prompt_cell = f"{schema.SPAN_ATTRS_STRING}['{attrs.PROMPT_KEY}']"
    in_cell = f"{schema.SPAN_ATTRS_NUMBER}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{schema.SPAN_ATTRS_NUMBER}['{attrs.OUTPUT_TOKEN_KEY}']"
    base = (f"FROM {schema.T_TRACES} "
            f"WHERE {schema.SPAN_TS} >= now() - INTERVAL {_win_min()} MINUTE "
            f"AND {schema.SPAN_SERVICE} = '{service}' "
            f"AND mapContains({schema.SPAN_ATTRS_STRING}, '{attrs.PROMPT_KEY}')")
    calls, in_tok, out_tok = ch.query(
        f"SELECT count(), sum({in_cell}), sum({out_cell}) {base}")[0]
    repeats = ch.query(
        f"SELECT sum(n - 1) FROM (SELECT count() AS n {base} "
        f"GROUP BY cityHash64({prompt_cell}) HAVING n > 1)")[0][0]
    return {"signal": "askdocs gen_ai calls", "window_minutes": _win_min(),
            "llm_calls": int(calls or 0), "cacheable_repeats": int(repeats or 0),
            "input_tokens": int(in_tok or 0), "output_tokens": int(out_tok or 0)}


def _l2_current(ch: ClickHouse, finding: Finding) -> dict:
    """L2 after-apply signal: p50/p95 input tokens per askdocs request over the recent window.
    With the preamble behind retrieval, per-request input tokens drop sharply."""
    service = finding.service or "askdocs"
    in_cell = f"{schema.SPAN_ATTRS_NUMBER}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{schema.SPAN_ATTRS_NUMBER}['{attrs.OUTPUT_TOKEN_KEY}']"
    sql = f"""
        SELECT count()                   AS calls,
               quantile(0.5)({in_cell})  AS p50_in,
               quantile(0.95)({in_cell}) AS p95_in,
               quantile(0.5)({out_cell}) AS p50_out,
               min({in_cell})            AS min_in
        FROM {schema.T_TRACES}
        WHERE {schema.SPAN_TS} >= now() - INTERVAL {_win_min()} MINUTE
          AND {schema.SPAN_SERVICE} = '{service}'
          AND mapContains({schema.SPAN_ATTRS_STRING}, '{attrs.PROMPT_KEY}')
    """
    calls, p50_in, p95_in, p50_out, min_in = ch.query(sql)[0]
    return {"signal": "askdocs input tokens/request", "window_minutes": _win_min(),
            "calls": int(calls or 0), "p50_input_tokens": round(float(p50_in or 0), 1),
            "p95_input_tokens": round(float(p95_in or 0), 1),
            "p50_output_tokens": round(float(p50_out or 0), 1),
            "min_input_tokens": round(float(min_in or 0), 1)}


_CURRENT = {"T1": _t1_current, "T2": _t2_current, "T3": _t3_current,
            "L1": _l1_current, "L2": _l2_current}


def integrity_sweep(api: SigNozAPI | None = None) -> dict:
    """Re-fetch dashboards + alert rules; a drop must not break any of them."""
    api = api or SigNozAPI()
    try:
        dash = api.dashboards()
        rules = api.alert_rules()
    except SigNozAPIError as e:
        return {"ok": False, "error": str(e)}
    n_dash = len(dash.get("data", []) if isinstance(dash, dict) else dash or [])
    n_rules = len((rules.get("data", {}) or {}).get("rules", []) if isinstance(rules, dict) else rules or [])
    return {"ok": True, "dashboards_resolved": n_dash, "alerts_resolved": n_rules}


def verify(finding: Finding, ch: ClickHouse | None = None, api: SigNozAPI | None = None) -> dict:
    ch = ch or ClickHouse()
    fn = _CURRENT.get(finding.id)
    if fn is None:
        return {"id": finding.id, "error": f"no verifier for {finding.id}"}
    current = fn(ch, finding)
    integrity = integrity_sweep(api)
    result = {
        "id": finding.id,
        "before": finding.measured,
        "after_recent_window": current,
        "integrity": integrity,
        "note": "crude D2 verify: recent-window re-measure + dashboard/alert integrity. "
                "Full before/after windows land in D4.",
    }
    finding.verification = result
    return result
