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


# ── L3 thresholds ──
# A retry storm (LEAK-CATALOG L3): the same prompt hammered several times in a short window with
# earlier attempts erroring. We lack a confirmed trace_id column on signoz_index_v3 (schema.py),
# so we cluster by (prompt_hash, 1-minute bucket) as a trace-less proxy and require >=1 error in
# the bucket — that error condition is what separates a retry burst from L1 duplicate traffic.
L3_MIN_ATTEMPTS = _f("L3_MIN_ATTEMPTS", 3)   # identical-prompt calls in a bucket to look like a burst


def detect_l3(ch: ClickHouse) -> Finding | None:
    """L3 · Retry storms: naive retry loops re-sending a failing prompt, each attempt billed.

    Recommend-only (LEAK-CATALOG): the fix is client-side backoff + a circuit breaker, suggested,
    never auto-applied. waste = input+output tokens on the errored attempts — spend that produced
    no usable answer. Returns None if the stack records no gen_ai errors (the safe, honest miss).
    """
    prompt_cell = f"{_STR}['{attrs.PROMPT_KEY}']"
    in_cell = f"{_NUM}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{_NUM}['{attrs.OUTPUT_TOKEN_KEY}']"
    is_llm = f"mapContains({_STR}, '{attrs.PROMPT_KEY}')"
    window = f"{schema.SPAN_TS} >= now() - INTERVAL {settings.audit_window_hours} HOUR"

    sql = f"""
        SELECT
            cityHash64({prompt_cell}) AS prompt_hash,
            toStartOfInterval({schema.SPAN_TS}, INTERVAL 1 MINUTE) AS bucket,
            count()                             AS attempts,
            countIf({schema.SPAN_HAS_ERROR})    AS errors,
            sum(if({schema.SPAN_HAS_ERROR}, {in_cell}, 0))  AS err_in,
            sum(if({schema.SPAN_HAS_ERROR}, {out_cell}, 0)) AS err_out,
            substring(any({prompt_cell}), 1, 200) AS sample
        FROM {schema.T_TRACES}
        WHERE {window} AND {schema.SPAN_SERVICE} = '{LLM_SERVICE}' AND {is_llm}
        GROUP BY prompt_hash, bucket
        HAVING attempts >= {int(L3_MIN_ATTEMPTS)} AND errors >= 1
        ORDER BY errors DESC, attempts DESC
    """
    rows = ch.query(sql)
    if not rows:
        return None

    storms = []
    wasted_in = wasted_out = 0.0
    failed_attempts = 0
    hashes = set()
    for prompt_hash, _bucket, attempts, errors, err_in, err_out, sample in rows:
        wasted_in += float(err_in or 0.0)
        wasted_out += float(err_out or 0.0)
        failed_attempts += int(errors or 0)
        hashes.add(str(prompt_hash))
        storms.append({
            "prompt_hash": str(prompt_hash),
            "attempts": int(attempts or 0),
            "failed_attempts": int(errors or 0),
            "wasted_input_tokens": round(float(err_in or 0.0)),
            "wasted_output_tokens": round(float(err_out or 0.0)),
            "sample_prompt": sample,
        })

    finding = Finding(
        id="L3",
        domain="llm",
        title="Retry storms",
        service=LLM_SERVICE,
        summary=(
            f"{len(storms)} retry burst(s) across {len(hashes)} distinct prompt(s) — "
            f"{failed_attempts:,} failed attempts re-sent within a minute, each billed for the "
            f"input it shipped. Naive retries multiply spend on transient failures."
        ),
        measured={
            "retry_bursts": storms,
            "distinct_prompts": len(hashes),
            "failed_attempts": failed_attempts,
            "wasted_input_tokens_window": round(wasted_in),
            "wasted_output_tokens_window": round(wasted_out),
            "min_attempts_threshold": int(L3_MIN_ATTEMPTS),
            "clustering": "prompt_hash x 1-minute bucket (trace-less proxy; no confirmed trace_id column)",
            "window_hours": settings.audit_window_hours,
        },
        money=money.tokens_monthly(wasted_in, wasted_out),
    )
    link = evidence.llm_spans_link(LLM_SERVICE)
    finding.add_evidence(Evidence(
        label=f"errored gen_ai spans for {LLM_SERVICE} in SigNoz Traces Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))
    # Recommend-only: nothing is dropped and nothing auto-applies; the suggestion is a client-side
    # backoff + circuit breaker so a transient failure stops fanning out into paid retries.
    finding.safety = {
        "safe": True,
        "proof": ("Recommendation only — no data dropped, nothing auto-applied. Add exponential "
                  "backoff + a circuit breaker on the askdocs LLM client so transient failures "
                  "stop multiplying token spend."),
        "references": [],
        "checked": {"auto_apply": False, "kind": "recommendation"},
    }
    finding.fix = {
        "kind": "recommendation",
        "target": LLM_SERVICE,
        "diff": (
            "# askdocs LLM client — suggested (not auto-applied)\n"
            "- resp = client.chat.completions.create(...)            # retried tightly on any error\n"
            "+ for attempt in range(MAX_RETRIES):                    # cap attempts\n"
            "+     try:\n"
            "+         resp = client.chat.completions.create(...)\n"
            "+         break\n"
            "+     except TransientError:\n"
            "+         sleep(BASE * 2 ** attempt + jitter)           # exponential backoff + jitter\n"
            "+ # trip a circuit breaker after N consecutive failures; fail fast instead of storming"
        ),
        "apply": "suggested, not auto-applied",
        "note": "Backoff + circuit breaker caps retry spend on transient failures. Client code change.",
        "path": "",
    }
    return finding


# ── L4 thresholds ──
L4_TRIVIAL_TOKENS = _f("L4_TRIVIAL_TOKENS", 300)     # input+output below this = a trivial lookup
L4_SAVINGS_FRACTION = _f("L4_SAVINGS_FRACTION", 0.9)  # assumed: a cheap tier serves it for ~1/10 the $
L4_MIN_CALLS = _f("L4_MIN_CALLS", 5)                 # ignore a handful of stray calls
# Expensive-tier model markers (a prefix/substring match). Cheap markers below always win, so
# "gpt-4o-mini" is NOT flagged even though it contains "gpt-4o". Configurable via env.
_L4_EXPENSIVE = [m.strip().lower() for m in os.getenv(
    "L4_EXPENSIVE_MODELS",
    "gpt-4o,gpt-4-turbo,gpt-4,gpt-4.1,o1,o3,claude-opus,claude-3-opus,claude-sonnet-4,claude-3-5-sonnet,gemini-1.5-pro",
).split(",") if m.strip()]
_L4_CHEAP_MARKERS = ("mini", "nano", "haiku", "flash", "small", "lite", "8b", "7b")


def _is_expensive_model(model: str) -> bool:
    m = (model or "").lower()
    if not m or any(c in m for c in _L4_CHEAP_MARKERS):
        return False
    return any(x in m for x in _L4_EXPENSIVE)


def detect_l4(ch: ClickHouse) -> Finding | None:
    """L4 · Model overkill: a flagship-tier model answering trivial short lookups.

    Recommend-only routing suggestion (LEAK-CATALOG). We aggregate trivial calls (input+output <
    threshold) per model, keep only expensive-tier models, and project the savings of routing them
    to a cheap tier (an assumed fraction, labeled). On a stack already on a mini/cheap model this
    returns None — which is the correct, honest result: no overkill to report.
    """
    model_cell = f"{_STR}['{attrs.MODEL_KEY}']"
    in_cell = f"{_NUM}['{attrs.INPUT_TOKEN_KEY}']"
    out_cell = f"{_NUM}['{attrs.OUTPUT_TOKEN_KEY}']"
    is_llm = f"mapContains({_STR}, '{attrs.PROMPT_KEY}')"
    window = f"{schema.SPAN_TS} >= now() - INTERVAL {settings.audit_window_hours} HOUR"

    sql = f"""
        SELECT {model_cell}   AS model,
               count()        AS calls,
               sum({in_cell})  AS in_tok,
               sum({out_cell}) AS out_tok
        FROM {schema.T_TRACES}
        WHERE {window} AND {schema.SPAN_SERVICE} = '{LLM_SERVICE}' AND {is_llm}
          AND ({in_cell} + {out_cell}) < {int(L4_TRIVIAL_TOKENS)}
          AND {model_cell} != ''
        GROUP BY model
        ORDER BY calls DESC
    """
    rows = ch.query(sql)
    if not rows:
        return None

    offenders = []
    in_sum = out_sum = 0.0
    calls_sum = 0
    for model, calls, in_tok, out_tok in rows:
        if not _is_expensive_model(str(model)):
            continue
        calls = int(calls or 0)
        offenders.append({
            "model": str(model),
            "trivial_calls": calls,
            "input_tokens": round(float(in_tok or 0.0)),
            "output_tokens": round(float(out_tok or 0.0)),
        })
        in_sum += float(in_tok or 0.0)
        out_sum += float(out_tok or 0.0)
        calls_sum += calls

    if not offenders or calls_sum < L4_MIN_CALLS:
        return None

    m = money.tokens_monthly(in_sum, out_sum)
    current = m["cost_month"]
    m["current_cost_month"] = current
    m["savings_fraction"] = L4_SAVINGS_FRACTION
    m["cost_month"] = round(current * L4_SAVINGS_FRACTION, 2)   # recoverable = projected saving
    m["rate_unit"] = "$/Mtok in|out (assumed); saving = current x assumed cheap-tier fraction"

    finding = Finding(
        id="L4",
        domain="llm",
        title="Model overkill",
        service=LLM_SERVICE,
        summary=(
            f"{calls_sum:,} trivial call(s) (<{int(L4_TRIVIAL_TOKENS)} tokens) are answered by a "
            f"flagship-tier model when a cheap tier would do. Routing them down projects "
            f"~{int(L4_SAVINGS_FRACTION * 100)}% off their current ${current:,.2f}/mo."
        ),
        measured={
            "offending_models": offenders,
            "trivial_calls": calls_sum,
            "trivial_token_ceiling": int(L4_TRIVIAL_TOKENS),
            "current_cost_month": current,
            "assumed_savings_fraction": L4_SAVINGS_FRACTION,
            "window_hours": settings.audit_window_hours,
        },
        money=m,
    )
    link = evidence.llm_spans_link(LLM_SERVICE)
    finding.add_evidence(Evidence(
        label=f"gen_ai spans for {LLM_SERVICE} by model in SigNoz Traces Explorer",
        deeplink=link["url"], filter=link["filter"], raw_query=" ".join(sql.split()),
    ))
    finding.safety = {
        "safe": True,
        "proof": ("Recommendation only — no data dropped, nothing auto-applied. Route trivial "
                  "short lookups to a cheap-tier model; keep the flagship for hard prompts. The "
                  "saving is an assumed cheap-tier rate fraction, labeled as such."),
        "references": [],
        "checked": {"auto_apply": False, "kind": "recommendation",
                    "savings_fraction": L4_SAVINGS_FRACTION},
    }
    finding.fix = {
        "kind": "recommendation",
        "target": LLM_SERVICE,
        "diff": (
            "# askdocs model routing — suggested (not auto-applied)\n"
            "- model = FLAGSHIP_MODEL                      # every request, regardless of difficulty\n"
            "+ model = CHEAP_MODEL if is_trivial(prompt) else FLAGSHIP_MODEL\n"
            "+ # is_trivial: short prompt / simple-lookup shape -> cheap tier; escalate on low confidence"
        ),
        "apply": "suggested, not auto-applied",
        "note": "Route trivial lookups to a cheap tier; escalate hard prompts. Savings labeled assumed.",
        "path": "",
    }
    return finding


DETECTORS = {"L1": detect_l1, "L2": detect_l2, "L3": detect_l3, "L4": detect_l4}


def run(ids: list[str] | None = None) -> list[Finding]:
    ch = ClickHouse()
    out: list[Finding] = []
    for fid, fn in DETECTORS.items():
        if ids and fid not in ids:
            continue
        # One detector must not sink the whole audit. A dead ClickHouse is a whole-stack problem
        # (fail loud, re-raise); any other per-detector error is logged and skipped so the working
        # detectors still return — matters most for the newer recommend-only L3/L4 on odd data.
        try:
            f = fn(ch)
        except ClickHouseUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[warn] LLM detector {fid} errored, skipping: {e}", file=sys.stderr)
            continue
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
