"""Pinned gen_ai span attribute keys for askdocs (Traceloop / OpenLLMetry).

VERIFIED against a real askdocs span (2026-07-21, provider=openai, model=gpt-4o-mini),
dumped from the collector debug exporter. The first key in each list below is the one this
stack actually emits; the rest are kept as fallbacks in case the OpenLLMetry version drifts.

Observed on the real span:
    gen_ai.provider.name       = openai
    gen_ai.operation.name      = chat
    gen_ai.request.model       = gpt-4o-mini
    gen_ai.response.model      = gpt-4o-mini-2024-07-18
    gen_ai.usage.input_tokens  = 54
    gen_ai.usage.output_tokens = 11
    gen_ai.usage.total_tokens  = 65
    gen_ai.usage.cache_read.input_tokens = 0
    gen_ai.input.messages / gen_ai.output.messages  (JSON arrays)

To re-verify after any dependency bump, pipe a span's attributes JSON in:

    python -m auditor.llm_auditor.attrs < one_span_attributes.json
"""
from __future__ import annotations

import json
import sys

# First entry = confirmed key on this stack; rest = cross-version fallbacks.
MODEL_KEYS = [
    "gen_ai.response.model",         # confirmed (exact model incl. dated suffix)
    "gen_ai.request.model",          # confirmed (requested alias)
    "llm.request.model",
]
INPUT_TOKEN_KEYS = [
    "gen_ai.usage.input_tokens",     # confirmed
    "gen_ai.usage.prompt_tokens",    # earlier OpenLLMetry
    "llm.usage.prompt_tokens",       # legacy Traceloop
]
OUTPUT_TOKEN_KEYS = [
    "gen_ai.usage.output_tokens",    # confirmed
    "gen_ai.usage.completion_tokens",
    "llm.usage.completion_tokens",
]
TOTAL_TOKEN_KEYS = [
    "gen_ai.usage.total_tokens",     # confirmed
    "llm.usage.total_tokens",
]
# Cached input tokens (0 when cache off) — relevant to the L1 cacheable-duplicates detector.
CACHE_READ_TOKEN_KEYS = [
    "gen_ai.usage.cache_read.input_tokens",  # confirmed
]
SYSTEM_KEYS = [
    "gen_ai.provider.name",          # confirmed ("openai")
    "gen_ai.system",                 # older semconv fallback
]
# This OpenLLMetry version emits prompts/completions as JSON arrays under single keys, not
# indexed (…prompt.0.content). Match the confirmed keys first, then the older indexed prefixes.
PROMPT_PREFIXES = ["gen_ai.input.messages", "gen_ai.prompt.", "llm.prompts."]
COMPLETION_PREFIXES = ["gen_ai.output.messages", "gen_ai.completion.", "llm.completions."]


# The confirmed key on THIS stack for each field (first entry of each list). ClickHouse detectors
# read a specific Map cell, so they need one exact key string, not the fallback list — the
# fallbacks matter only when parsing a live span dict via resolve_usage() below.
MODEL_KEY = MODEL_KEYS[0]
INPUT_TOKEN_KEY = INPUT_TOKEN_KEYS[0]
OUTPUT_TOKEN_KEY = OUTPUT_TOKEN_KEYS[0]
PROMPT_KEY = PROMPT_PREFIXES[0]          # "gen_ai.input.messages" — full request messages JSON


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
    cache_key, cache_read_tokens = _first(attrs, CACHE_READ_TOKEN_KEYS)

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = int(input_tokens) + int(output_tokens)
        total_key = "(computed: input+output)"

    return {
        "system": system,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_read_tokens": cache_read_tokens,
        "_source_keys": {
            "system": sys_key,
            "model": model_key,
            "input_tokens": in_key,
            "output_tokens": out_key,
            "total_tokens": total_key,
            "cache_read_tokens": cache_key,
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
