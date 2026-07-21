"""LLM-waste detectors (domain L), mined from askdocs gen_ai spans. L1 first.

Same contract as the telemetry detectors (telemetry_auditor/detectors.py): read ONLY names
pinned against the live instance (trace tables/columns in schema.py, gen_ai attribute keys in
llm_auditor/attrs.py), compute $ via money.py (shown, not hidden), attach a SigNoz deep-link +
the raw ClickHouse query as evidence, and fail loud on query errors (golden rule #7).

gen_ai spans carry the request messages and token usage as span attributes, stored in the typed
Maps on signoz_index_v3. We hash the full request-messages string per span and group by that
hash over the window: identical prompts answered fresh every time are L1 waste. The fix is a
config flip in askdocs (exact-match, TTL-bounded cache) — represented as a diff, not a collector
patch — so L1 does not go through fixgen; detection is what this module owns.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from auditor.config import settings
from auditor.llm_auditor import attrs
from auditor.telemetry_auditor import evidence, money, schema
from auditor.telemetry_auditor.clickhouse import ClickHouse, ClickHouseUnavailable
from auditor.telemetry_auditor.findings import Evidence, Finding, Status

LLM_SERVICE = os.getenv("ASKDOCS_SERVICE_NAME", "askdocs")


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "")) if os.getenv(name) else default
    except ValueError:
        return default


# ── L1 thresholds ──
# A prompt hash seen >= this many times in the window is a cacheable duplicate (catalog: count>=5).
L1_MIN_DUPES = _f("L1_MIN_DUPES", 5)

_NUM = schema.SPAN_ATTRS_NUMBER   # Map(String,Float64): token counts
_STR = schema.SPAN_ATTRS_STRING   # Map(String,String): request messages, model


def detect_l1(ch: ClickHouse) -> Finding | None:
    """L1 · Cacheable duplicates: identical prompts answered fresh every time.

    waste = sum over duplicated prompt-hashes of (count-1) x avg tokens of that hash — i.e. every
    repeat after the first, which an exact-match cache would have served for free.
    """
    prompt_cell = f"{_STR}['{attrs.PROMPT_KEY}']"
    in_cell = f"{_NUM}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{_NUM}['{attrs.OUTPUT_TOKEN_KEY}']"
    # A span is a gen_ai/LLM call iff it carries the request-messages attribute.
    is_llm = f"mapContains({_STR}, '{attrs.PROMPT_KEY}')"
    window = f"{schema.SPAN_TS} >= now() - INTERVAL {settings.audit_window_hours} HOUR"

    sql = f"""
        SELECT
            cityHash64({prompt_cell}) AS prompt_hash,
            count()                   AS n,
            avg({in_cell})            AS avg_in,
            avg({out_cell})           AS avg_out,
            substring(any({prompt_cell}), 1, 200) AS sample
        FROM {schema.T_TRACES}
        WHERE {window} AND {schema.SPAN_SERVICE} = '{LLM_SERVICE}' AND {is_llm}
        GROUP BY prompt_hash
        HAVING n >= {int(L1_MIN_DUPES)}
        ORDER BY n DESC
    """
    rows = ch.query(sql)
    if not rows:
        return None

    dupes = []
    wasted_in = wasted_out = 0.0
    for prompt_hash, n, avg_in, avg_out, sample in rows:
        n = int(n)
        repeats = n - 1  # the first call is unavoidable; only repeats are cacheable
        w_in = repeats * float(avg_in or 0.0)
        w_out = repeats * float(avg_out or 0.0)
        wasted_in += w_in
        wasted_out += w_out
        dupes.append({
            "prompt_hash": str(prompt_hash),
            "count": n,
            "repeats": repeats,
            "avg_input_tokens": round(float(avg_in or 0.0), 1),
            "avg_output_tokens": round(float(avg_out or 0.0), 1),
            "wasted_input_tokens": round(w_in),
            "wasted_output_tokens": round(w_out),
            "sample_prompt": sample,
        })

    total_calls = sum(d["count"] for d in dupes)
    total_repeats = sum(d["repeats"] for d in dupes)

    finding = Finding(
        id="L1",
        domain="llm",
        title="Cacheable duplicate prompts",
        service=LLM_SERVICE,
        summary=(
            f"{len(dupes)} distinct prompt(s) were answered fresh {total_calls:,} times "
            f"({total_repeats:,} exact repeats) — every repeat is a cache miss paid in full."
        ),
        measured={
            "duplicate_prompts": dupes,
            "distinct_prompts": len(dupes),
            "total_calls": total_calls,
            "total_repeats": total_repeats,
            "wasted_input_tokens_window": round(wasted_in),
            "wasted_output_tokens_window": round(wasted_out),
            "min_dupes_threshold": int(L1_MIN_DUPES),
            "window_hours": settings.audit_window_hours,
        },
        money=money.tokens_monthly(wasted_in, wasted_out),
    )

    link = evidence.llm_spans_link(LLM_SERVICE)
    finding.add_evidence(Evidence(
        label=f"gen_ai spans for {LLM_SERVICE} in SigNoz Traces Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))
    # L1 safety is categorical, not a cross-reference: the fix is an exact-match, TTL-bounded
    # cache. It only ever returns a byte-identical prior answer to a byte-identical prompt — no
    # semantic guessing, so there is zero wrong-answer risk. Stated plainly (LEAK-CATALOG L1).
    finding.safety = {
        "safe": True,
        "proof": ("Fix = exact-match, TTL-bounded response cache. A cached answer is returned "
                  "only for a byte-identical prompt; no semantic matching, so no wrong-answer "
                  "risk. Non-repeat traffic is unaffected."),
        "references": [],
        "checked": {"cache_type": "exact-match sha256(question)", "ttl_seconds": int(_f("ASKDOCS_CACHE_TTL", 3600))},
    }
    return finding


# ── L2 thresholds ──
L2_BLOAT_RATIO = _f("L2_BLOAT_RATIO", 8.0)          # flag when p50 input > ratio x p50 output
L2_MIN_OVERHEAD = _f("L2_MIN_OVERHEAD", 800)        # min shared-overhead tokens worth flagging
L2_PREFIX_ALLOWANCE = _f("L2_PREFIX_ALLOWANCE", 500)  # a lean prompt is allowed this much context
L2_MIN_CALLS = _f("L2_MIN_CALLS", 5)                # ignore endpoints with almost no traffic


def detect_l2(ch: ClickHouse) -> Finding | None:
    """L2 · Prompt bloat: a huge static preamble glued to every request regardless of question.

    Every request carries the same shared context, so the MINIMUM observed input tokens is a
    measured proxy for that fixed overhead (the shortest question still ships the whole preamble).
    Flag when input dwarfs output (p50_in > ratio x p50_out) and that overhead is large. waste =
    (min_input - allowance) x request_count — the context that should live behind retrieval.
    """
    in_cell = f"{_NUM}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{_NUM}['{attrs.OUTPUT_TOKEN_KEY}']"
    is_llm = f"mapContains({_STR}, '{attrs.PROMPT_KEY}')"
    window = f"{schema.SPAN_TS} >= now() - INTERVAL {settings.audit_window_hours} HOUR"

    sql = f"""
        SELECT count()                       AS calls,
               quantile(0.5)({in_cell})      AS p50_in,
               quantile(0.95)({in_cell})     AS p95_in,
               quantile(0.5)({out_cell})     AS p50_out,
               min({in_cell})                AS min_in
        FROM {schema.T_TRACES}
        WHERE {window} AND {schema.SPAN_SERVICE} = '{LLM_SERVICE}' AND {is_llm}
    """
    row = ch.query(sql)
    if not row:
        return None
    calls, p50_in, p95_in, p50_out, min_in = row[0]
    calls = int(calls or 0)
    p50_in, p95_in, p50_out, min_in = (float(p50_in or 0), float(p95_in or 0),
                                       float(p50_out or 0), float(min_in or 0))
    if calls < L2_MIN_CALLS:
        return None
    ratio = (p50_in / p50_out) if p50_out else float("inf")
    overhead = min_in  # the fixed preamble every request pays for
    if ratio < L2_BLOAT_RATIO or overhead < L2_MIN_OVERHEAD:
        return None

    bloat_per_req = max(0.0, overhead - L2_PREFIX_ALLOWANCE)
    wasted_in = bloat_per_req * calls

    finding = Finding(
        id="L2",
        domain="llm",
        title="Prompt bloat",
        service=LLM_SERVICE,
        summary=(
            f"Every request ships ~{int(overhead):,} tokens of shared context "
            f"(p50 input {int(p50_in):,} vs p50 output {int(p50_out):,} = {ratio:.0f}x); "
            f"{int(bloat_per_req):,} of them (beyond a {int(L2_PREFIX_ALLOWANCE)}-token allowance) "
            f"belong behind retrieval, not glued to every prompt."
        ),
        measured={
            "calls": calls,
            "p50_input_tokens": round(p50_in, 1),
            "p95_input_tokens": round(p95_in, 1),
            "p50_output_tokens": round(p50_out, 1),
            "min_input_tokens": round(min_in, 1),
            "input_output_ratio": round(ratio, 2) if ratio != float("inf") else None,
            "shared_overhead_tokens": round(overhead, 1),
            "prefix_allowance_tokens": int(L2_PREFIX_ALLOWANCE),
            "bloat_tokens_per_request": round(bloat_per_req, 1),
            "wasted_input_tokens_window": round(wasted_in),
            "window_hours": settings.audit_window_hours,
        },
        money=money.tokens_monthly(wasted_in, 0),
    )
    link = evidence.llm_spans_link(LLM_SERVICE)
    finding.add_evidence(Evidence(
        label=f"gen_ai spans for {LLM_SERVICE} (input-token size) in SigNoz Traces Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))
    # L2 fix = move static context behind retrieval (askdocs already has the RAG path; the wasteful
    # mode bypasses it). Not a drop of anyone's data, so safety is categorical, not a cross-check.
    finding.safety = {
        "safe": True,
        "proof": ("Fix routes the static preamble through the existing retrieval path instead of "
                  "gluing the full doc set to every prompt. Answers still draw from the same docs; "
                  "only the redundant context bytes shrink. No data dropped, fully reversible."),
        "references": [],
        "checked": {"shared_overhead_tokens": round(overhead, 1), "allowance": int(L2_PREFIX_ALLOWANCE)},
    }
    return finding


DETECTORS = {"L1": detect_l1, "L2": detect_l2}


def run(ids: list[str] | None = None) -> list[Finding]:
    ch = ClickHouse()
    out: list[Finding] = []
    for fid, fn in DETECTORS.items():
        if ids and fid not in ids:
            continue
        f = fn(ch)
        if f is not None:
            f.status = Status.DETECTED
            out.append(f)
    return out


def _print_table(findings: list[Finding]) -> None:
    if not findings:
        print("no LLM-waste findings (thresholds not met on current data).")
        return
    print(f"{'ID':<4} {'TITLE':<28} {'SERVICE':<10} {'$/MONTH':>9}  {'SAFE':<5} EVIDENCE")
    print("-" * 96)
    for f in findings:
        safe = "yes" if f.safety.get("safe") else "NO"
        url = f.evidence[0].deeplink if f.evidence else ""
        print(f"{f.id:<4} {f.title:<28} {f.service:<10} ${f.cost_month:>8.2f}  {safe:<5} {url[:40]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="llm-detectors", description="Run LLM-waste detectors")
    p.add_argument("ids", nargs="*", help="subset e.g. L1; default all")
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
