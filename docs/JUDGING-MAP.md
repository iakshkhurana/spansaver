# Judging Map — criteria → what we show

**Track: AI & Agent Observability** — *trace, monitor, and debug AI-native systems.* SpanSaver is
an autonomous agent that observes AI + infra through SigNoz, detects problems, and **self-heals**
(closest to example build #5, "Self-healing infra with SigNoz metrics"). It even traces its own
LLM calls, so it audits its own AI cost. The LLM/agent-observability half (L1/L2, Agent Ops,
`/explain`) leads; the telemetry-cost half (T1–T4) is the same closed loop applied to infra.

This table is mirrored live on the `/judge` page of Mission Control. The "Where" column points
at the exact evidence — a UI route, a repo file, or a SigNoz view — so every claim is one click
from proof.

| # | Criterion | What we show | Where |
|---|-----------|--------------|-------|
| 1 | Potential Impact | Real $/month recovered on a live stack across the two universal bills (telemetry + tokens); savings ticker; the SigNoz Cost Meter roadmap gap we fill | Mission Control home (`/`) · [PITCH.md](PITCH.md) |
| 2 | Creativity & Innovation | A self-healing agent that closes the loop on AI *and* infra waste; the safety-proof step; it audits its own AI cost via a real traced LLM call (`POST /explain/<id>` → `spansaver-auditor` gen_ai spans) | `/leak/L1` cache proof · `/leak/T2` safety proof · Explain-with-AI on `/leak/[id]` · Agent Ops dashboard |
| 3 | Technical Excellence | ClickHouse introspection ([schema.py](../auditor/telemetry_auditor/schema.py)), OTTL patch generation with validation + rollback ([fixgen](../auditor/fixgen/generate.py)), before/after verify with an integrity sweep ([verify.py](../auditor/verifier/verify.py)), a live command console | [`collector/patches/`](../collector/) · [`auditor/`](../auditor/) code tour |
| 4 | Best Use of SigNoz | Reads: ClickHouse tables, dashboards API, alert-rules API, Metrics Explorer. Writes: patches upstream of SigNoz + importable dashboards, **and its own `gen_ai` spans** (the auditor traces its explainer LLM call back into SigNoz as `spansaver-auditor`). Plus the SigNoz MCP server used during development | [signoz_api.py](../auditor/telemetry_auditor/signoz_api.py) · [explainer.py](../auditor/llm_auditor/explainer.py) · [dashboards/agent-ops.json](../dashboards/agent-ops.json) · [SETUP.md](SETUP.md) |
| 5 | User Experience | One-screen leak report, evidence deep-links, one-tap Apply, before→after green banner, a working front terminal, Judge Mode itself | Mission Control (`/`) · `/leak/[id]` · `/judge` |
| 6 | Presentation Quality | 3:00 demo where every claim is clicked, not asserted; `make demo` reproduces the whole loop hands-free; honest limitations section | [DEMO-SCRIPT.md](DEMO-SCRIPT.md) · [README](../README.md) quickstart |

## The one-liner per criterion (memorize)
1. "It finds real dollars, today, in the two bills every team pays."
2. "A self-healing agent for AI + infra waste — the loop includes proof, and it even audits its own AI cost."
3. "It fixes the pipeline the way a platform team would: reviewable patches, validated, reversible, and verified."
4. "SigNoz is both our data source and our verification instrument."
5. "Every finding is two clicks: see the evidence, apply the fix."
6. "Three minutes, zero slides, every number live — or `make demo` runs it hands-free."

## Live proof cheat-sheet (numbers from the 2026-07-22 run — refresh before recording)
- **$80.13/mo** leaking across **5 findings, 2 domains** (T2 $57.96 · T4 $11.58 · L1 $9.85 · T3 $0.72 · T1 $0.02).
- **T2** — 7 orphan metrics, referenced by 0 dashboards / 0 alerts (proof, not guess).
- **T4** — `checkout_latency_ms` exploded to thousands of series by a per-user `user_id` label; the fix drops just that label (OTTL `delete_key`), keeping the metric.
- **T1 / L1** — apply → verify → **down 100%**, integrity intact — the green banner, on real metrics.
