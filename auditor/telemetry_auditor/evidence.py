"""SigNoz deep-link builders — every finding must carry a link into SigNoz (golden rule #3).

These build URLs into the correct SigNoz Explorer (logs / traces / metrics) scoped to the
audit window, plus a human-readable filter. The exact compositeQuery URL-encoding SigNoz uses
is version-specific and best verified in-browser (a D3 polish item); until then a finding also
carries its raw ClickHouse query as primary, non-repudiable evidence. Base paths below are for
SigNoz v0.133 and read from SIGNOZ_UI_URL — never hardcode the host (golden rule #5).
"""
from __future__ import annotations

from urllib.parse import urlencode

from auditor.config import settings

# Explorer base paths confirmed for the v0.133 UI.
PATH_LOGS = "/logs/logs-explorer"
PATH_TRACES = "/traces-explorer"
PATH_METRICS = "/metrics-explorer/explorer"


def _link(path: str, filter_expr: str, relative_minutes: int | None = None) -> dict:
    """Return {url, filter} for an explorer view. `filter` is the human/KQL expression to apply;
    it is also passed as a query hint. relative time defaults to the audit window."""
    minutes = relative_minutes if relative_minutes is not None else settings.audit_window_hours * 60
    params = {"relativeTime": f"{minutes}m", "filter": filter_expr}
    return {
        "url": f"{settings.signoz_ui_url.rstrip('/')}{path}?{urlencode(params)}",
        "filter": filter_expr,
    }


def logs_link(service: str, extra: str = "") -> dict:
    """Deep-link into Logs Explorer for a service (optionally with an extra filter clause)."""
    expr = f"service.name = '{service}'" + (f" AND {extra}" if extra else "")
    return _link(PATH_LOGS, expr)


def traces_link(filter_expr: str) -> dict:
    """Deep-link into Traces Explorer with a filter, e.g. httpRoute IN ('/healthz')."""
    return _link(PATH_TRACES, filter_expr)


def metrics_link(metric_name: str) -> dict:
    """Deep-link into Metrics Explorer for a metric (base name; SigNoz splits histograms)."""
    return _link(PATH_METRICS, f"metric_name = '{metric_name}'")
