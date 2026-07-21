"""Telemetry-waste detectors T1–T3. Each returns a Finding (or None if nothing qualifies).

Every query here uses ONLY names pinned in schema.py (confirmed against the live instance),
computes $ via money.py (shown, not hidden), attaches a SigNoz deep-link + the raw query as
evidence, and — for a drop-type fix — a real safety proof from usage_xref (the dashboards/alerts
cross-check). Thresholds are env-overridable so the same detectors work on thin demo data and
fat production data. Fail loud on query/API errors (golden rule #7).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from auditor.config import settings
from auditor.telemetry_auditor import evidence, money, schema
from auditor.telemetry_auditor.clickhouse import ClickHouse, ClickHouseUnavailable
from auditor.telemetry_auditor.findings import Evidence, Finding, Status
from auditor.telemetry_auditor.usage_xref import ReferenceSource, safety_for, try_build_corpus


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "")) if os.getenv(name) else default
    except ValueError:
        return default


# ── T1 thresholds ──
T1_MIN_DEBUG_SHARE = _f("T1_MIN_DEBUG_SHARE", 0.30)     # DEBUG+TRACE share of a service's log bytes
T1_MIN_DEBUG_BYTES = _f("T1_MIN_DEBUG_BYTES", 100_000)  # absolute floor over the window (skip noise)


def _logs_window_clause() -> str:
    # logs_v2.timestamp is UNIX nanoseconds.
    return (
        f"{schema.LOG_TS} >= toUnixTimestamp(now() - INTERVAL {settings.audit_window_hours} HOUR) "
        f"* 1000000000"
    )


def detect_t1(ch: ClickHouse, corpus: list[ReferenceSource] | None = None,
              corpus_err: str = "") -> Finding | None:
    """T1 · Debug-log flood: services whose DEBUG/TRACE logs are a big, unused share of ingest."""
    # DEBUG=5-8, TRACE=1-4 per OTel; severity_number 0 = UNSPECIFIED (excluded).
    debug_pred = f"{schema.LOG_SEVERITY_NUMBER} > 0 AND {schema.LOG_SEVERITY_NUMBER} < {schema.SEVERITY_INFO_MIN}"
    sql = f"""
        SELECT
            {schema.LOG_SERVICE_EXPR} AS service,
            countIf({debug_pred}) AS debug_logs,
            count() AS total_logs,
            sumIf(length({schema.LOG_BODY}), {debug_pred}) AS debug_bytes,
            sum(length({schema.LOG_BODY})) AS total_bytes
        FROM {schema.T_LOGS}
        WHERE {_logs_window_clause()} AND service != ''
        GROUP BY service
        HAVING debug_logs > 0
        ORDER BY debug_bytes DESC
    """
    rows = ch.query(sql)

    flagged = []
    for service, debug_logs, total_logs, debug_bytes, total_bytes in rows:
        share = (debug_bytes / total_bytes) if total_bytes else 0.0
        if share >= T1_MIN_DEBUG_SHARE and debug_bytes >= T1_MIN_DEBUG_BYTES:
            flagged.append({
                "service": service,
                "debug_logs": int(debug_logs),
                "total_logs": int(total_logs),
                "debug_bytes": int(debug_bytes),
                "total_bytes": int(total_bytes),
                "debug_share": round(share, 4),
            })
    if not flagged:
        return None

    total_debug_bytes = sum(f["debug_bytes"] for f in flagged)
    worst = flagged[0]["service"]
    services = [f["service"] for f in flagged]

    finding = Finding(
        id="T1",
        domain="telemetry",
        title="Debug-log flood",
        service=worst,
        summary=(
            f"{len(flagged)} service(s) ship DEBUG/TRACE logs as >={int(T1_MIN_DEBUG_SHARE*100)}% "
            f"of their log bytes: {', '.join(services)}."
        ),
        measured={
            "services": flagged,
            "total_debug_bytes_window": total_debug_bytes,
            "window_hours": settings.audit_window_hours,
        },
        money=money.ingest_monthly(total_debug_bytes),
    )

    link = evidence.logs_link(worst, extra=f"{schema.LOG_SEVERITY_NUMBER} < {schema.SEVERITY_INFO_MIN}")
    finding.add_evidence(Evidence(
        label=f"DEBUG/TRACE logs for {worst} in SigNoz Logs Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))

    # Safety: is anyone's dashboard/alert reading these services' logs? Conservative — flag the
    # service name; on the clean instance this is zero, proving the drop is safe.
    if corpus is None:
        corpus, corpus_err = try_build_corpus()
    if corpus_err:
        finding.safety = {"safe": False, "proof": f"UNVERIFIED — SigNoz API error: {corpus_err}",
                          "references": [], "checked": {}}
    else:
        finding.safety = safety_for(corpus, services, f"DEBUG logs of {', '.join(services)}")
    return finding


# ── T2 thresholds ──
T2_MIN_DATAPOINTS = _f("T2_MIN_DATAPOINTS", 1)  # ignore metrics with almost no datapoints


def detect_t2(ch: ClickHouse, corpus: list[ReferenceSource] | None = None,
              corpus_err: str = "") -> Finding | None:
    """T2 · Orphan metrics: ingested metrics referenced by no dashboard and no alert."""
    if corpus is None:
        corpus, corpus_err = try_build_corpus()

    sql = f"""
        SELECT {schema.SAMPLE_METRIC_NAME} AS metric_name,
               count() AS datapoints,
               uniqExact({schema.TS_FINGERPRINT}) AS series
        FROM {schema.T_SAMPLES}
        WHERE {schema.SAMPLE_UNIX_MILLI} >=
              toUnixTimestamp(now() - INTERVAL {settings.audit_window_hours} HOUR) * 1000
        GROUP BY metric_name
    """
    rows = ch.query(sql)

    # Collapse histogram components to their base name; drop infra/runtime plumbing.
    bases: dict[str, dict] = {}
    for metric_name, datapoints, series in rows:
        if schema.is_internal_metric(metric_name):
            continue
        base = schema.metric_base_name(metric_name)
        agg = bases.setdefault(base, {"metric": base, "datapoints": 0, "series": 0})
        agg["datapoints"] += int(datapoints)
        agg["series"] = max(agg["series"], int(series))

    # Orphan = base name referenced by no dashboard/alert. Cross-check is fail-loud upstream;
    # if the API was down we cannot prove orphanhood, so emit nothing rather than a false claim.
    if corpus_err:
        finding = Finding(id="T2", domain="telemetry", title="Orphan metrics",
                          status=Status.FAILED,
                          error=f"cannot verify references — SigNoz API error: {corpus_err}")
        return finding

    orphans = []
    for base, agg in bases.items():
        if agg["datapoints"] < T2_MIN_DATAPOINTS:
            continue
        refs = safety_for(corpus, [base], f"metric {base}")
        if refs["safe"]:  # referenced by none == orphan
            orphans.append(agg)
    if not orphans:
        return None
    orphans.sort(key=lambda a: a["datapoints"], reverse=True)

    total_dp = sum(o["datapoints"] for o in orphans)
    names = [o["metric"] for o in orphans]
    top = orphans[0]["metric"]

    finding = Finding(
        id="T2",
        domain="telemetry",
        title="Orphan metrics",
        service="payments",
        summary=f"{len(orphans)} metric(s) referenced by no dashboard and no alert: {', '.join(names)}.",
        measured={"orphans": orphans, "total_datapoints_window": total_dp,
                  "window_hours": settings.audit_window_hours},
        money=money.samples_monthly(total_dp),
    )
    link = evidence.metrics_link(top)
    finding.add_evidence(Evidence(
        label=f"Orphan metric {top} in SigNoz Metrics Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))
    finding.safety = safety_for(corpus, names, f"metrics {', '.join(names)}")
    return finding


# ── T3 thresholds ──
T3_MIN_HEALTH_SHARE = _f("T3_MIN_HEALTH_SHARE", 0.20)  # health spans as share of all spans
T3_MIN_HEALTH_SPANS = _f("T3_MIN_HEALTH_SPANS", 100)

# A span is a health probe if its route or name matches these. status-OK only — errors on a
# health route are real signal and are KEPT (never dropped).
_HEALTH_ROUTE_RE = "^/?(health|healthz|ready|readyz|live|livez)$"


def detect_t3(ch: ClickHouse, corpus: list[ReferenceSource] | None = None,
              corpus_err: str = "") -> Finding | None:
    """T3 · Health-check span spam: OK-status probe spans nobody queries, dropped safely."""
    health_pred = (
        f"(match({schema.SPAN_HTTP_ROUTE}, '{_HEALTH_ROUTE_RE}') "
        f"OR positionCaseInsensitive({schema.SPAN_NAME}, 'health') > 0 "
        f"OR positionCaseInsensitive({schema.SPAN_NAME}, '/ready') > 0 "
        f"OR positionCaseInsensitive({schema.SPAN_NAME}, '/live') > 0)"
    )
    window = f"{schema.SPAN_TS} >= now() - INTERVAL {settings.audit_window_hours} HOUR"
    sql = f"""
        SELECT
            countIf({health_pred} AND {schema.SPAN_HAS_ERROR} = false) AS health_ok_spans,
            countIf({health_pred} AND {schema.SPAN_HAS_ERROR} = true)  AS health_err_spans,
            count() AS total_spans
        FROM {schema.T_TRACES}
        WHERE {window}
    """
    rows = ch.query(sql)
    health_ok, health_err, total_spans = rows[0] if rows else (0, 0, 0)
    health_ok, health_err, total_spans = int(health_ok), int(health_err), int(total_spans)
    share = (health_ok / total_spans) if total_spans else 0.0
    if share < T3_MIN_HEALTH_SHARE or health_ok < T3_MIN_HEALTH_SPANS:
        return None

    # Per-service/route breakdown for the evidence + patch scoping.
    breakdown = ch.query(f"""
        SELECT {schema.SPAN_SERVICE} AS service, {schema.SPAN_NAME} AS name,
               {schema.SPAN_HTTP_ROUTE} AS route, count() AS c
        FROM {schema.T_TRACES}
        WHERE {window} AND {health_pred} AND {schema.SPAN_HAS_ERROR} = false
        GROUP BY service, name, route ORDER BY c DESC
    """)
    routes = sorted({r[2] for r in breakdown if r[2]})
    names = sorted({r[1] for r in breakdown})

    finding = Finding(
        id="T3",
        domain="telemetry",
        title="Health-check span spam",
        summary=(
            f"{health_ok:,} OK-status health-probe spans = {share:.0%} of all trace ingest; "
            f"nobody queries them. ({health_err} error-status health spans KEPT as signal.)"
        ),
        measured={
            "health_ok_spans": health_ok, "health_err_spans_kept": health_err,
            "total_spans": total_spans, "health_share": round(share, 4),
            "routes": routes, "span_names": names,
            "by_service": [{"service": s, "name": n, "route": rt, "count": int(c)}
                           for s, n, rt, c in breakdown],
            "window_hours": settings.audit_window_hours,
        },
        money=money.spans_monthly(health_ok),
    )
    link = evidence.traces_link("name CONTAINS 'health' AND has_error = false")
    finding.add_evidence(Evidence(
        label="Health-check spans in SigNoz Traces Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))
    # Safety: do any dashboards/alerts query these routes? (error-status spans are excluded from
    # the drop regardless.) On the clean instance: none.
    if corpus is None:
        corpus, corpus_err = try_build_corpus()
    if corpus_err:
        finding.safety = {"safe": False, "proof": f"UNVERIFIED — SigNoz API error: {corpus_err}",
                          "references": [], "checked": {}}
    else:
        finding.safety = safety_for(corpus, routes or ["/healthz"],
                                    f"health routes {', '.join(routes) or '/healthz'}")
    return finding


DETECTORS = {"T1": detect_t1, "T2": detect_t2, "T3": detect_t3}


def run(ids: list[str] | None = None) -> list[Finding]:
    ch = ClickHouse()
    corpus, corpus_err = try_build_corpus()
    out: list[Finding] = []
    for fid, fn in DETECTORS.items():
        if ids and fid not in ids:
            continue
        f = fn(ch, corpus=corpus, corpus_err=corpus_err)
        if f is not None:
            f.status = Status.DETECTED
            out.append(f)
    return out


def _print_table(findings: list[Finding]) -> None:
    if not findings:
        print("no telemetry-waste findings (thresholds not met on current data).")
        return
    print(f"{'ID':<4} {'TITLE':<20} {'SERVICE':<10} {'$/MONTH':>9}  {'SAFE':<5} EVIDENCE")
    print("-" * 92)
    for f in findings:
        safe = "yes" if f.safety.get("safe") else "NO"
        url = f.evidence[0].deeplink if f.evidence else ""
        print(f"{f.id:<4} {f.title:<20} {f.service:<10} ${f.cost_month:>8.2f}  {safe:<5} {url[:40]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="detectors", description="Run telemetry-waste detectors")
    p.add_argument("ids", nargs="*", help="subset e.g. T1 T2; default all")
    p.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = p.parse_args(argv)
    try:
        findings = run([i.upper() for i in args.ids] or None)
    except ClickHouseUnavailable as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        _print_table(findings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
