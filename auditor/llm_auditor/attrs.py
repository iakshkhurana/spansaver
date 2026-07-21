"""Pinned gen_ai span attribute keys for askdocs (Traceloop / OpenLLMetry).

⚠️ UNVERIFIED STUB — the exact keys depend on the installed OpenLLMetry version. Golden
rule #1 (introspect, don't guess): dump ONE real askdocs span and confirm which keys are
present, then NARROW each candidate list below to the single key you observed and drop this
warning. Until then the resolver tries every known candidate in order.

To dump a span's attributes once the stack is running, pipe its attributes JSON in:

    python -m auditor.llm_auditor.attrs < one_span_attributes.json

(Get that JSON from the collector `debug` exporter output, the SigNoz trace view's raw
span, or a ClickHouse `signoz_traces` query — whichever is handy.)
"""
from __future__ import annotations

import json
import sys

# Candidate keys, most-current OTel gen_ai semconv first, then legacy OpenLLMetry/Traceloop.
# NARROW each list to the one confirmed key after dumping a real span.
MODEL_KEYS = [
    "gen_ai.response.model",
    "gen_ai.request.model",
    "llm.request.model",
]
INPUT_TOKEN_KEYS = [
    "gen_ai.usage.input_tokens",     # current OTel semconv
    "gen_ai.usage.prompt_tokens",    # earlier OpenLLMetry
    "llm.usage.prompt_tokens",       # legacy Traceloop
]
OUTPUT_TOKEN_KEYS = [
    "gen_ai.usage.output_tokens",
    "gen_ai.usage.completion_tokens",
    "llm.usage.completion_tokens",
]
TOTAL_TOKEN_KEYS = [
    "gen_ai.usage.total_tokens",
    "llm.usage.total_tokens",
]
SYSTEM_KEYS = [
    "gen_ai.system",                 # e.g. "anthropic" / "openai"
]
# Prompt/completion content is indexed (…prompt.0.content, …completion.0.role). We match by
# prefix rather than exact key.
PROMPT_PREFIXES = ["gen_ai.prompt.", "llm.prompts."]
COMPLETION_PREFIXES = ["gen_ai.completion.", "llm.completions."]


def _first(attrs: dict, keys: list[str]):
    """Return (key, value) for the first candidate present, else (None, None)."""
    for k in keys:
        if k in attrs and attrs[k] is not None:
            return k, attrs[k]
    return None, None


def resolve_usage(attrs: dict) -> dict:
    """Extract model + token usage from a span's attribute dict, version-agnostically.

    Returns a dict with resolved values AND the exact source key each came from, so callers
    (and you, during verification) can see which convention this instance actually emits.
    """
    model_key, model = _first(attrs, MODEL_KEYS)
    in_key, input_tokens = _first(attrs, INPUT_TOKEN_KEYS)
    out_key, output_tokens = _first(attrs, OUTPUT_TOKEN_KEYS)
    total_key, total_tokens = _first(attrs, TOTAL_TOKEN_KEYS)
    sys_key, system = _first(attrs, SYSTEM_KEYS)

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = int(input_tokens) + int(output_tokens)
        total_key = "(computed: input+output)"

    return {
        "system": system,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "_source_keys": {
            "system": sys_key,
            "model": model_key,
            "input_tokens": in_key,
            "output_tokens": out_key,
            "total_tokens": total_key,
        },
    }


def _report(attrs: dict) -> None:
    """Print which candidate keys fired — the verification aid for pinning."""
    resolved = resolve_usage(attrs)
    print("resolved usage:")
    for field in ("system", "model", "input_tokens", "output_tokens", "total_tokens"):
        src = resolved["_source_keys"][field]
        print(f"  {field:<14} = {resolved[field]!r:<24} (from {src})")

    prompt_keys = [k for k in attrs if any(k.startswith(p) for p in PROMPT_PREFIXES)]
    completion_keys = [k for k in attrs if any(k.startswith(p) for p in COMPLETION_PREFIXES)]
    print(f"  prompt keys    = {prompt_keys}")
    print(f"  completion keys= {completion_keys}")

    missing = [f for f in ("model", "input_tokens", "output_tokens") if resolved[f] is None]
    if missing:
        print(f"\n[!] no candidate matched for: {missing} -- add the real key(s) to attrs.py")
    else:
        print("\n[OK] all core fields resolved -- narrow each *_KEYS list to the 'from' keys above")


if __name__ == "__main__":
    raw = sys.stdin.read()
    if not raw.strip():
        print("usage: python -m auditor.llm_auditor.attrs < span_attributes.json", file=sys.stderr)
        sys.exit(1)
    _report(json.loads(raw))
