"""The ONE place the auditor itself calls an LLM.

Turns a Finding into a plain-English explanation via an LLM. The call is instrumented with
Traceloop (OpenLLMetry) — the same pipeline askdocs uses — so the auditor's own gen_ai spans land
in SigNoz under service `spansaver-auditor`. That is what makes "SpanSaver audits its own AI cost"
literally true: this run's tokens show up in the Agent Ops dashboard, and the returned `usage` is
priced with the same assumed $/Mtok rates as every finding (golden rule #2, labeled "assumed").

Provider-agnostic, mirroring askdocs: LLM_PROVIDER selects openai | anthropic. Traceloop
auto-instruments whichever client is used, so the tracing (and the self-cost disclosure) holds
either way. Everything fails loud (golden rule #7): no key, no SDK, or a dead collector each raise
a clear ExplainerError that /explain surfaces as a 502 — never a silent fake explanation.
"""
from __future__ import annotations

import os
import threading

from auditor.config import settings
from auditor.telemetry_auditor.findings import Finding

_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
_DEFAULT_MODEL = {"anthropic": "claude-opus-4-8", "openai": "gpt-4o-mini"}
_MODEL = os.getenv("EXPLAINER_MODEL") or _DEFAULT_MODEL.get(_PROVIDER, "gpt-4o-mini")
_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
_MAX_TOKENS = int(os.getenv("EXPLAINER_MAX_TOKENS", "400"))

_init_lock = threading.Lock()
_initialized = False


class ExplainerError(RuntimeError):
    pass


def _ensure_traceloop() -> None:
    """Init Traceloop once so the LLM client auto-instruments and its gen_ai spans export to OUR
    collector (same pipeline askdocs uses). Idempotent + thread-safe; must run before the first
    LLM call."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from traceloop.sdk import Traceloop

            Traceloop.init(
                app_name="spansaver-auditor",
                exporter=OTLPSpanExporter(endpoint=_OTLP_ENDPOINT, insecure=True),
                disable_batch=True,   # flush each span immediately (shows up in SigNoz fast)
            )
        except Exception as e:  # noqa: BLE001 - surface any init failure loudly
            raise ExplainerError(
                f"could not initialise Traceloop/OTLP ({_OTLP_ENDPOINT}): {e}. Add traceloop-sdk + "
                "opentelemetry-exporter-otlp to auditor/requirements and rebuild the auditor image."
            ) from e
        _initialized = True


_SYSTEM = (
    "You are SpanSaver's explainer. You describe an already-detected observability/LLM waste "
    "finding in plain English for a platform engineer. Never invent metrics — use only what is "
    "given. Keep it tight and concrete."
)


def _prompt(f: Finding) -> str:
    return (
        f"Finding {f.id} ({f.domain}): {f.title}\n"
        f"Summary: {f.summary}\n"
        f"Estimated waste: ${f.money.get('cost_month')}/month\n"
        f"Safety proof: {f.safety.get('proof', '')}\n\n"
        "In 2-3 sentences, explain what this waste is, why the fix is safe, and what the fix does. "
        "Be concrete; use only the numbers given — do not invent any."
    )


def _call(prompt: str) -> tuple[str, int, int]:
    """Return (text, input_tokens, output_tokens) from the configured provider."""
    if _PROVIDER == "openai":
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ExplainerError("openai SDK not installed — add it to auditor/requirements and rebuild.") from e
        if not os.getenv("OPENAI_API_KEY"):
            raise ExplainerError("OPENAI_API_KEY not set — the auditor needs a key to explain findings.")
        try:
            resp = OpenAI().chat.completions.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            )
        except Exception as e:  # noqa: BLE001
            raise ExplainerError(f"LLM call failed: {e}") from e
        text = (resp.choices[0].message.content or "").strip()
        u = resp.usage
        return text, int(u.prompt_tokens), int(u.completion_tokens)

    # default: anthropic
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise ExplainerError("anthropic SDK not installed — add it to auditor/requirements and rebuild.") from e
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ExplainerError("ANTHROPIC_API_KEY not set — the auditor needs a key to explain findings.")
    try:
        resp = Anthropic().messages.create(
            model=_MODEL, max_tokens=_MAX_TOKENS, system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:  # noqa: BLE001
        raise ExplainerError(f"LLM call failed: {e}") from e
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, int(resp.usage.input_tokens), int(resp.usage.output_tokens)


def explain(f: Finding) -> dict:
    """Make a real, traced LLM call to explain `f`. Returns {explanation, model, usage, cost}."""
    _ensure_traceloop()
    text, in_tok, out_tok = _call(_prompt(f))
    cost = round((in_tok / 1_000_000) * settings.price_in_per_mtok
                 + (out_tok / 1_000_000) * settings.price_out_per_mtok, 4)
    result = {
        "explanation": text,
        "provider": _PROVIDER,
        "model": _MODEL,
        "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
        "cost_usd": cost,
        "rate_unit": "$/Mtok in|out (assumed)",
        "traced": "gen_ai spans emitted to SigNoz as service 'spansaver-auditor' (Agent Ops)",
    }
    f.explanation = result
    return result
