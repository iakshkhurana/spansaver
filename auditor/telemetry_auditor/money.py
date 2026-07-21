"""$ math — measured volume × assumed rate, extrapolated to 30 days.

Golden rule #2: the only assumptions allowed are the pricing rates (from .env), and they must
be shown, never hidden. Every function here returns a dict that includes the inputs, the
extrapolation factor, and the rate used — so the UI can render "we measured X in the window,
that's Y/day, at $Z/GB that's $N/month" instead of a bare number. Nothing here invents volume.
"""
from __future__ import annotations

from auditor.config import settings

# Decimal GB for ingest billing (1e9 bytes). Observability vendors vary GB vs GiB; the rate is
# labeled "assumed" regardless, and this constant is surfaced so the basis is explicit.
BYTES_PER_GB = 1_000_000_000
DAYS_PER_MONTH = 30
TOKENS_PER_MTOK = 1_000_000


def _per_month_factor(window_hours: float) -> float:
    """Scale a per-window measurement to a 30-day month."""
    if window_hours <= 0:
        return 0.0
    return (24.0 / window_hours) * DAYS_PER_MONTH


def ingest_monthly(bytes_in_window: float, window_hours: float | None = None) -> dict:
    """Project ingest $/month from bytes measured over the audit window."""
    window_hours = settings.audit_window_hours if window_hours is None else window_hours
    factor = _per_month_factor(window_hours)
    gb_window = bytes_in_window / BYTES_PER_GB
    gb_month = gb_window * factor
    cost_month = gb_month * settings.price_per_gb_ingest
    return {
        "bytes_window": round(bytes_in_window),
        "gb_window": round(gb_window, 4),
        "window_hours": window_hours,
        "extrapolation_factor": round(factor, 3),
        "gb_month": round(gb_month, 3),
        "rate": settings.price_per_gb_ingest,
        "rate_unit": "$/GB ingested (assumed)",
        "cost_month": round(cost_month, 2),
        "basis": f"{BYTES_PER_GB:,} bytes = 1 GB",
    }


def _per_million_monthly(count_window: float, rate: float, unit: str,
                         window_hours: float | None = None) -> dict:
    """Project $/month for a per-million-item rate (metrics datapoints, spans)."""
    window_hours = settings.audit_window_hours if window_hours is None else window_hours
    factor = _per_month_factor(window_hours)
    count_month = count_window * factor
    cost_month = (count_month / 1_000_000) * rate
    return {
        "count_window": round(count_window),
        "window_hours": window_hours,
        "extrapolation_factor": round(factor, 3),
        "count_month": round(count_month),
        "rate": rate,
        "rate_unit": unit,
        "cost_month": round(cost_month, 2),
    }


def samples_monthly(datapoints_in_window: float, window_hours: float | None = None) -> dict:
    """Metrics $/month from datapoints measured over the window (rate assumed, per Mdatapoints)."""
    return _per_million_monthly(
        datapoints_in_window, settings.price_per_million_samples,
        "$/M datapoints (assumed)", window_hours,
    )


def spans_monthly(spans_in_window: float, window_hours: float | None = None) -> dict:
    """Traces $/month from span count measured over the window (rate assumed, per Mspans)."""
    return _per_million_monthly(
        spans_in_window, settings.price_per_million_spans,
        "$/M spans (assumed)", window_hours,
    )


def tokens_monthly(input_tokens: float, output_tokens: float, window_hours: float | None = None) -> dict:
    """Project LLM token $/month from input/output tokens measured over the window."""
    window_hours = settings.audit_window_hours if window_hours is None else window_hours
    factor = _per_month_factor(window_hours)
    in_month = input_tokens * factor
    out_month = output_tokens * factor
    cost_in = (in_month / TOKENS_PER_MTOK) * settings.price_in_per_mtok
    cost_out = (out_month / TOKENS_PER_MTOK) * settings.price_out_per_mtok
    return {
        "input_tokens_window": round(input_tokens),
        "output_tokens_window": round(output_tokens),
        "window_hours": window_hours,
        "extrapolation_factor": round(factor, 3),
        "input_tokens_month": round(in_month),
        "output_tokens_month": round(out_month),
        "rate_in": settings.price_in_per_mtok,
        "rate_out": settings.price_out_per_mtok,
        "rate_unit": "$/Mtok in|out (assumed)",
        "cost_month": round(cost_in + cost_out, 2),
    }
