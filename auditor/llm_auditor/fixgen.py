"""fixgen for LLM findings — the fix here is a config flip, not a collector patch.

L1's fix is enabling askdocs' exact-match, TTL-bounded response cache (LEAK-CATALOG L1: "the
generated 'patch' here is a config change + a diff shown in the UI"). So instead of a collector
YAML we emit a unified-diff-style file into collector/generated/ (inert — merge_config.py only
globs collector/patches/*.yaml, so nothing activates until /apply restarts askdocs with the new
env) and attach it to the finding for the UI to render. Same honesty contract as the collector
fixgen: generating a fix never activates it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from auditor.config import settings
from auditor.telemetry_auditor.findings import Finding, Status

# askdocs env before -> after. Cache off + nocache-forced  ->  cache on, no bypass.
_L1_ENV_DIFF = [
    ("WASTE_LLM_NOCACHE", "1", "0"),  # stop forcing the uncached "before" path
    ("ASKDOCS_CACHE", "0", "1"),      # turn the exact-match response cache on
]


def _l1_diff_text(f: Finding) -> str:
    ttl = f.safety.get("checked", {}).get("ttl_seconds", 3600)
    lines = [
        "# askdocs service env (docker compose env / .env) — L1 fix",
        "# Exact-match response cache: returns a byte-identical prior answer only for a",
        f"# byte-identical prompt, TTL {ttl}s. No semantic matching, so no wrong-answer risk.",
        "",
    ]
    for key, old, new in _L1_ENV_DIFF:
        lines.append(f"- {key}={old}")
        lines.append(f"+ {key}={new}")
    return "\n".join(lines) + "\n"


def generate_l1_fix(finding: Finding) -> str:
    """Write the L1 config diff into the STAGED dir and populate finding.fix. Returns the path
    and sets status=FIX_READY. /apply restarts askdocs with the new env; generating does not."""
    diff = _l1_diff_text(finding)
    os.makedirs(settings.generated_dir, exist_ok=True)
    path = os.path.join(settings.generated_dir, "L1.diff")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    header = (
        f"# SpanSaver generated fix -- finding {finding.id}: {finding.title}\n"
        f"# generated-at: {ts}\n"
        f"# {finding.summary}\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + "\n" + diff)

    finding.fix = {
        "kind": "config",
        "target": "askdocs",
        "diff": diff,
        "apply": "restart askdocs with ASKDOCS_CACHE=1 and WASTE_LLM_NOCACHE=0",
        "note": "Exact-match, TTL-bounded cache — no code change, reversible by flipping the env back.",
        "path": path,
    }
    finding.status = Status.FIX_READY
    return path


def _l2_diff_text(f: Finding) -> str:
    overhead = f.measured.get("shared_overhead_tokens")
    allowance = f.measured.get("prefix_allowance_tokens", 500)
    lines = [
        "# askdocs service env (docker compose env / .env) — L2 fix",
        "# Stop gluing the full doc set into every prompt; route static context through the",
        f"# existing retrieval path instead. Shared overhead ~{overhead} tokens/request drops",
        f"# to a lean {allowance}-token allowance. Same docs, fewer redundant input bytes.",
        "",
        "- WASTE_LLM_BLOAT=1",
        "+ WASTE_LLM_BLOAT=0",
    ]
    return "\n".join(lines) + "\n"


def generate_l2_fix(finding: Finding) -> str:
    """Write the L2 config diff into the STAGED dir and populate finding.fix (status=FIX_READY)."""
    diff = _l2_diff_text(finding)
    os.makedirs(settings.generated_dir, exist_ok=True)
    path = os.path.join(settings.generated_dir, "L2.diff")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    header = (f"# SpanSaver generated fix -- finding {finding.id}: {finding.title}\n"
              f"# generated-at: {ts}\n# {finding.summary}\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + "\n" + diff)

    finding.fix = {
        "kind": "config",
        "target": "askdocs",
        "diff": diff,
        "apply": "restart askdocs with WASTE_LLM_BLOAT=0 (static context moves behind retrieval)",
        "note": "Answers still draw from the same docs; only redundant prompt context shrinks. Reversible.",
        "path": path,
    }
    finding.status = Status.FIX_READY
    return path


_BUILDERS = {"L1": generate_l1_fix, "L2": generate_l2_fix}


def generate_fix(finding: Finding) -> str:
    """Dispatch an LLM finding to its fix generator. Raises if the id has no generator."""
    builder = _BUILDERS.get(finding.id)
    if builder is None:
        raise ValueError(f"no LLM fix generator for finding {finding.id}")
    return builder(finding)


if __name__ == "__main__":
    # Smoke test with a synthetic L1 finding — no ClickHouse needed.
    demo = Finding(id="L1", domain="llm", title="Cacheable duplicate prompts", service="askdocs",
                   summary="10 prompts answered fresh 250 times",
                   safety={"checked": {"ttl_seconds": 3600}})
    p = generate_fix(demo)
    print(f"=== {p} ===")
    print(open(p, encoding="utf-8").read())
    print("finding.fix:", demo.fix["kind"], "->", demo.fix["apply"])
