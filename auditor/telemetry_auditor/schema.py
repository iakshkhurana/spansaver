"""Pinned SigNoz ClickHouse schema — CONFIRMED against the live instance, not guessed.

VERIFIED 2026-07-21 against SigNoz on clickhouse-server 25.12.5 via
`auditor.telemetry_auditor.introspect` (and direct `system.columns` dumps). This is the
telemetry-side analogue of llm_auditor/attrs.py: detectors import names from here so no table
or column string is ever hardcoded inline. Re-run introspect.py after any SigNoz upgrade and
update the constants + the VERIFIED date below.

Architecture notes (this SigNoz is the v3/v4 generation):
  * Read through the `distributed_*` tables — they fan out across shards and are correct on a
    single node too. The plain (local) tables are what `system.parts` reports sizes for.
  * Logs live in `logs_v2`; `service.name` is a resource attribute in the `resources_string`
    Map, i.e. resources_string['service.name']. `timestamp` is UInt64 UNIX NANOSECONDS.
  * Traces use `signoz_index_v3`, which conveniently flattens common fields into columns:
    `serviceName`, `httpRoute`, `name` (span name), `has_error` (Bool), `duration_nano`.
    `timestamp` is DateTime64(9) — compare directly to now()/DateTime, NOT to nanoseconds.
  * Metrics: one row per (fingerprint) in `time_series_v4` == one active series, so
    uniqExact(fingerprint) per metric_name == series/cardinality. Datapoints are rows in
    `samples_v4` (`unix_milli` Int64 epoch millis, `value` Float64). Histograms are split by
    SigNoz into suffixed metric_names: `<name>.bucket|.count|.sum|.min|.max`.
"""
from __future__ import annotations

# ─── Databases ────────────────────────────────────────────────────────────────
DB_LOGS = "signoz_logs"
DB_TRACES = "signoz_traces"
DB_METRICS = "signoz_metrics"

# ─── Tables: query through distributed_*, size via the local table ────────────
# Logs
T_LOGS = f"{DB_LOGS}.distributed_logs_v2"
T_LOGS_LOCAL = f"{DB_LOGS}.logs_v2"
T_LOGS_USAGE = f"{DB_LOGS}.distributed_usage"

# Traces
T_TRACES = f"{DB_TRACES}.distributed_signoz_index_v3"
T_TRACES_LOCAL = f"{DB_TRACES}.signoz_index_v3"

# Metrics
T_TIME_SERIES = f"{DB_METRICS}.distributed_time_series_v4"   # one row per series (fingerprint)
T_TIME_SERIES_LOCAL = f"{DB_METRICS}.time_series_v4"
T_SAMPLES = f"{DB_METRICS}.distributed_samples_v4"           # datapoints
T_SAMPLES_LOCAL = f"{DB_METRICS}.samples_v4"

# ─── Logs columns ─────────────────────────────────────────────────────────────
LOG_TS = "timestamp"                 # UInt64, UNIX nanoseconds
LOG_SEVERITY_TEXT = "severity_text"  # LowCardinality(String): INFO/DEBUG/WARN/...
LOG_SEVERITY_NUMBER = "severity_number"  # UInt8, OTel severity number
LOG_BODY = "body"                    # String; byte proxy = length(body)
LOG_RESOURCES = "resources_string"   # Map(String,String); service.name lives here
LOG_SERVICE_EXPR = "resources_string['service.name']"

# OTel severity numbers: TRACE 1-4, DEBUG 5-8, INFO 9-12, WARN 13-16, ERROR 17-20, FATAL 21-24.
# "< INFO" (i.e. DEBUG/TRACE) is the T1 drop boundary.
SEVERITY_INFO_MIN = 9

# ─── Traces columns (signoz_index_v3) ─────────────────────────────────────────
SPAN_TS = "timestamp"                # DateTime64(9); compare to now() directly
SPAN_SERVICE = "serviceName"         # LowCardinality(String)
SPAN_NAME = "name"                   # LowCardinality(String); e.g. "GET /healthz"
SPAN_HTTP_ROUTE = "httpRoute"        # LowCardinality(String); e.g. "/healthz"
SPAN_HTTP_URL = "httpUrl"
SPAN_HAS_ERROR = "has_error"         # Bool; errors on health routes are KEPT (signal)
SPAN_DURATION_NANO = "duration_nano"

# ─── Metrics columns ──────────────────────────────────────────────────────────
TS_METRIC_NAME = "metric_name"       # LowCardinality(String)
TS_FINGERPRINT = "fingerprint"       # UInt64; distinct count == active series (cardinality)
TS_LABELS = "labels"                 # String (JSON of the label set)
TS_ATTRS = "attrs"                   # Map(String,String)
TS_UNIX_MILLI = "unix_milli"         # Int64 epoch millis
SAMPLE_METRIC_NAME = "metric_name"
SAMPLE_UNIX_MILLI = "unix_milli"
SAMPLE_VALUE = "value"

# Metric-name prefixes/suffixes that are SigNoz-internal, collector self-telemetry, language
# runtime, or Prometheus scrape plumbing. Used to avoid false positives in the T2 orphan-metric
# set difference (never recommend dropping infra's own metrics). Confirmed against the live
# metric universe on 2026-07-21: otelcol_*, signoz_*, http.*, asyncio.*, scrape_*, up.
METRIC_INTERNAL_PREFIXES = ("signoz_", "chi_", "clickhouse_", "otelcol_")
METRIC_RUNTIME_PREFIXES = (
    "system_", "process_", "runtime_", "http_", "rpc_", "k8s_", "container_",
    "asyncio_", "scrape_", "net_", "db_", "messaging_", "python_",
)
# Exact metric names that are infra plumbing (Prometheus meta-metrics).
METRIC_INTERNAL_EXACT = ("up", "target_info", "scrape_series_added")
# Histogram/summary component suffixes appended to the base metric_name by SigNoz.
METRIC_COMPONENT_SUFFIXES = (".bucket", ".count", ".sum", ".min", ".max")


def metric_base_name(name: str) -> str:
    """Strip a histogram/summary component suffix to recover the base metric name."""
    for suf in METRIC_COMPONENT_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def is_internal_metric(name: str) -> bool:
    """True if a metric is infra/runtime plumbing and must be excluded from orphan detection.
    OTel emits dotted names (http.server.duration); SigNoz may keep dots — normalize to '_'
    before prefix-matching so both forms are caught."""
    base = metric_base_name(name)
    norm = base.replace(".", "_").lower()
    if norm in METRIC_INTERNAL_EXACT:
        return True
    return norm.startswith(METRIC_INTERNAL_PREFIXES + METRIC_RUNTIME_PREFIXES)
