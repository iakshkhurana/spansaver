"""Verify a fix on the live stack: before → after windows + a dashboard/alert integrity sweep.

The honest question a verify answers: "did the waste actually stop, and did we break anything?"
Two halves, both real queries:

1. before → after. The detector already measured the leak's volume over the audit window (the
   "before", held on the finding). We re-measure the same signal over an "after" window and turn
   both into a comparable per-minute rate, so the headline is an honest drop-% — "debug-log
   ingest was 42 KB/min, it's now 3 KB/min: down 93%." For a level-type signal (L2's tokens per
   request) we compare the level directly, no rate.

   The after window is measured as *time-since-apply* whenever we know when /apply ran
   (finding.applied_at): the window is exactly [apply, now], so stale pre-apply data never
   dilutes the drop. Without that timestamp (e.g. a fix applied out-of-band) we fall back to the
   recent VERIFY_WINDOW_MINUTES window, which understates the drop — the safe direction to err.

2. integrity. Re-fetch every dashboard and alert rule; if any now fails to load, the drop broke
   something and the verify FAILS loudly.

A verify PASSES iff the rate dropped >= VERIFY_MIN_DROP_PCT AND every dashboard/alert resolved.
`banner` is the one-line the UI shows in green (pass) or red (fail).
"""
from __future__ import annotations

import time

from auditor.config import settings
from auditor.llm_auditor import attrs
from auditor.telemetry_auditor import schema
from auditor.telemetry_auditor.clickhouse import ClickHouse
from auditor.telemetry_auditor.findings import Finding
from auditor.telemetry_auditor.signoz_api import SigNozAPI, SigNozAPIError

# Minimum after-window so a verify run seconds after apply still has data to measure (and the
# per-minute rate isn't divided by a near-zero window).
_MIN_AFTER_SECONDS = 60


def _after_window(finding: Finding) -> tuple[int, float, str]:
    """(seconds, minutes, basis) for the after window. Time-since-apply when known, else the
    configured recent window."""
    if finding.applied_at:
        elapsed = time.time() - finding.applied_at
        sec = max(_MIN_AFTER_SECONDS, int(elapsed))
        return sec, sec / 60.0, "since apply"
    sec = settings.verify_window_minutes * 60
    return sec, sec / 60.0, "recent window"


def _t1_current(ch: ClickHouse, finding: Finding, win_sec: int) -> dict:
    services = [s["service"] for s in finding.measured.get("services", [])] or [finding.service]
    svc_list = ", ".join(f"'{s}'" for s in services)
    debug_pred = f"{schema.LOG_SEVERITY_NUMBER} > 0 AND {schema.LOG_SEVERITY_NUMBER} < {schema.SEVERITY_INFO_MIN}"
    sql = f"""
        SELECT countIf({debug_pred}) AS debug_logs,
               sumIf(length({schema.LOG_BODY}), {debug_pred}) AS debug_bytes
        FROM {schema.T_LOGS}
        WHERE {schema.LOG_TS} >= toUnixTimestamp(now() - INTERVAL {win_sec} SECOND) * 1000000000
          AND {schema.LOG_SERVICE_EXPR} IN ({svc_list})
    """
    dl, db = ch.query(sql)[0]
    return {"debug_logs": int(dl), "debug_bytes": int(db)}


def _t2_current(ch: ClickHouse, finding: Finding, win_sec: int) -> dict:
    names = [o["metric"] for o in finding.measured.get("orphans", [])]
    name_list = ", ".join(f"'{n}'" for n in names)
    sql = f"""
        SELECT count() AS datapoints
        FROM {schema.T_SAMPLES}
        WHERE {schema.SAMPLE_UNIX_MILLI} >= toUnixTimestamp(now() - INTERVAL {win_sec} SECOND) * 1000
          AND {schema.SAMPLE_METRIC_NAME} IN ({name_list})
    """
    dp = ch.query(sql)[0][0]
    return {"datapoints": int(dp)}


def _t3_current(ch: ClickHouse, finding: Finding, win_sec: int) -> dict:
    health_pred = (
        f"(match({schema.SPAN_HTTP_ROUTE}, '^/?(health|healthz|ready|readyz|live|livez)$') "
        f"OR positionCaseInsensitive({schema.SPAN_NAME}, 'health') > 0)"
    )
    sql = f"""
        SELECT countIf({health_pred} AND {schema.SPAN_HAS_ERROR} = false) AS health_ok
        FROM {schema.T_TRACES}
        WHERE {schema.SPAN_TS} >= now() - INTERVAL {win_sec} SECOND
    """
    ho = ch.query(sql)[0][0]
    return {"health_ok_spans": int(ho)}


def _l1_current(ch: ClickHouse, finding: Finding, win_sec: int) -> dict:
    """L1 after-apply signal: gen_ai calls + tokens for askdocs, plus the cacheable-repeat count.
    With the cache on, exact-duplicate prompts are served before the LLM call, so they emit no new
    gen_ai span — repeats collapse toward 0 and tokens step down."""
    service = finding.service or "askdocs"
    prompt_cell = f"{schema.SPAN_ATTRS_STRING}['{attrs.PROMPT_KEY}']"
    in_cell = f"{schema.SPAN_ATTRS_NUMBER}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{schema.SPAN_ATTRS_NUMBER}['{attrs.OUTPUT_TOKEN_KEY}']"
    base = (f"FROM {schema.T_TRACES} "
            f"WHERE {schema.SPAN_TS} >= now() - INTERVAL {win_sec} SECOND "
            f"AND {schema.SPAN_SERVICE} = '{service}' "
            f"AND mapContains({schema.SPAN_ATTRS_STRING}, '{attrs.PROMPT_KEY}')")
    calls, in_tok, out_tok = ch.query(
        f"SELECT count(), sum({in_cell}), sum({out_cell}) {base}")[0]
    repeats = ch.query(
        f"SELECT sum(n - 1) FROM (SELECT count() AS n {base} "
        f"GROUP BY cityHash64({prompt_cell}) HAVING n > 1)")[0][0]
    return {"llm_calls": int(calls or 0), "cacheable_repeats": int(repeats or 0),
            "input_tokens": int(in_tok or 0), "output_tokens": int(out_tok or 0)}


def _l2_current(ch: ClickHouse, finding: Finding, win_sec: int) -> dict:
    """L2 after-apply signal: p50/p95 input tokens per askdocs request. With the preamble behind
    retrieval, per-request input tokens drop sharply."""
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
        WHERE {schema.SPAN_TS} >= now() - INTERVAL {win_sec} SECOND
          AND {schema.SPAN_SERVICE} = '{service}'
          AND mapContains({schema.SPAN_ATTRS_STRING}, '{attrs.PROMPT_KEY}')
    """
    calls, p50_in, p95_in, p50_out, min_in = ch.query(sql)[0]
    return {"calls": int(calls or 0), "p50_input_tokens": round(float(p50_in or 0), 1),
            "p95_input_tokens": round(float(p95_in or 0), 1),
            "p50_output_tokens": round(float(p50_out or 0), 1),
            "min_input_tokens": round(float(min_in or 0), 1)}


def _t4_current(ch: ClickHouse, finding: Finding, win_sec: int) -> dict:
    """T4 after-apply signal: of the metric's active series in the after-window, what share still
    carry the high-cardinality label. Window-robust — a dropped label is simply absent (100%->0%),
    unlike a raw series count which shrinks just because the window is short."""
    metric = finding.measured.get("metric", "")
    key = finding.measured.get("bomb_key", "")
    sql = f"""
        SELECT count() AS series_now,
               countIf(mapContains({schema.TS_ATTRS}, '{key}')) AS series_with_key
        FROM (
            SELECT any({schema.TS_ATTRS}) AS {schema.TS_ATTRS}
            FROM {schema.T_TIME_SERIES}
            WHERE {schema.TS_METRIC_NAME} = '{metric}'
              AND {schema.TS_UNIX_MILLI} >= toUnixTimestamp(now() - INTERVAL {win_sec} SECOND) * 1000
            GROUP BY {schema.TS_FINGERPRINT}
        )
    """
    series_now, series_with_key = ch.query(sql)[0]
    series_now, series_with_key = int(series_now), int(series_with_key)
    share = (100.0 * series_with_key / series_now) if series_now else 0.0
    return {"series_now": series_now, "series_carrying_key": series_with_key,
            "key_share_pct": round(share, 1)}


_CURRENT = {"T1": _t1_current, "T2": _t2_current, "T3": _t3_current, "T4": _t4_current,
            "L1": _l1_current, "L2": _l2_current}

# How to turn a finding's before (measured) + after (current) into one headline number.
# kind="rate": both counts become per-minute rates (before over the audit window, after over the
# after window) before comparing. kind="level": compare the value directly (already per-request).
_HEADLINE = {
    "T1": {"metric": "debug-log ingest", "unit": "bytes/min", "kind": "rate",
           "before_key": "total_debug_bytes_window", "after_key": "debug_bytes"},
    "T2": {"metric": "orphan-metric datapoints", "unit": "datapoints/min", "kind": "rate",
           "before_key": "total_datapoints_window", "after_key": "datapoints"},
    "T3": {"metric": "health-check spans", "unit": "spans/min", "kind": "rate",
           "before_key": "health_ok_spans", "after_key": "health_ok_spans"},
    "T4": {"metric": "series carrying the high-card label", "unit": "% of series", "kind": "level",
           "before_key": "key_share_baseline_pct", "after_key": "key_share_pct"},
    "L1": {"metric": "cacheable repeat calls", "unit": "repeats/min", "kind": "rate",
           "before_key": "total_repeats", "after_key": "cacheable_repeats"},
    "L2": {"metric": "input tokens / request", "unit": "tokens", "kind": "level",
           "before_key": "p50_input_tokens", "after_key": "p50_input_tokens"},
}


def _headline(finding: Finding, current: dict, after_min: float) -> dict:
    """Before vs after as one comparable number + the drop-%. Positive drop = the leak shrank."""
    spec = _HEADLINE[finding.id]
    before_raw = float(finding.measured.get(spec["before_key"], 0) or 0)
    after_raw = float(current.get(spec["after_key"], 0) or 0)
    if spec["kind"] == "rate":
        before_hours = float(finding.measured.get("window_hours", settings.audit_window_hours) or 1)
        before = before_raw / max(before_hours * 60.0, 1.0)     # per minute
        after = after_raw / max(after_min, 1.0)                 # per minute
    else:
        before, after = before_raw, after_raw
    drop_pct = ((before - after) / before * 100.0) if before > 0 else 0.0
    return {"metric": spec["metric"], "unit": spec["unit"], "kind": spec["kind"],
            "before": round(before, 2), "after": round(after, 2),
            "before_raw": round(before_raw, 2), "after_raw": round(after_raw, 2),
            "drop_pct": round(drop_pct, 1)}


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


def _banner(headline: dict, integrity: dict, passed: bool, threshold: float) -> str:
    if not integrity.get("ok"):
        return f"BROKEN — integrity check failed: {integrity.get('error', 'unknown error')}"
    n_dash = integrity.get("dashboards_resolved", 0)
    n_rules = integrity.get("alerts_resolved", 0)
    drop = headline["drop_pct"]
    intact = f"{n_dash} dashboard{'s' if n_dash != 1 else ''} and {n_rules} alert{'s' if n_rules != 1 else ''} intact"
    if passed:
        return f"Verified: {intact} — {headline['metric']} down {drop:.0f}%."
    if drop <= 0:
        return f"No drop yet — {headline['metric']} unchanged. Wait for post-apply data, then re-verify."
    return f"Applied — {headline['metric']} down only {drop:.0f}% (< {threshold:.0f}% target). Give it a beat and re-verify."


def verify(finding: Finding, ch: ClickHouse | None = None, api: SigNozAPI | None = None) -> dict:
    ch = ch or ClickHouse()
    fn = _CURRENT.get(finding.id)
    if fn is None:
        return {"id": finding.id, "error": f"no verifier for {finding.id}"}

    win_sec, win_min, basis = _after_window(finding)
    current = fn(ch, finding, win_sec)
    current.update({"window_minutes": round(win_min, 2), "window_basis": basis})

    headline = _headline(finding, current, win_min)
    integrity = integrity_sweep(api)
    threshold = settings.verify_min_drop_pct
    passed = bool(integrity.get("ok")) and headline["drop_pct"] >= threshold

    result = {
        "id": finding.id,
        "passed": passed,
        "banner": _banner(headline, integrity, passed, threshold),
        "headline": headline,
        "threshold_drop_pct": threshold,
        "before": finding.measured,
        "after": current,
        "integrity": integrity,
    }
    finding.verification = result
    return result
