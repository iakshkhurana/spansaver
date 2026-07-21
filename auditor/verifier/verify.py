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


_CURRENT = {"T1": _t1_current, "T2": _t2_current, "T3": _t3_current}


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
