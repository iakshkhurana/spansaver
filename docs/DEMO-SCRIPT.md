# Demo Script — 3:00, shot by shot

Layout: browser A = Mission Control, browser B = SigNoz. Pre-seeded via `make demo`
(waste on, ≥24h of data or accelerated equivalent, audit already run once so findings are
warm — we re-run live for authenticity).

> **Numbers below are REAL, from the live `make demo` run on 2026-07-22.** They scale with how
> long traffic has run — re-run `make demo` right before the final recording and refresh any
> figure that drifted. Totals: **$80.13/mo across 5 findings, 2 domains.** (Per-finding: T2
> $57.96 · T4 $11.58 · L1 $9.85 · T3 $0.72 · T1 $0.02.)

**0:00–0:20 · The hook (say the dollar number in the first sentence)**
> "This stack is quietly leaking money in five places no dashboard will ever flag — and
> SpanSaver found all five in seconds, across two bills nobody audits together: observability
> bytes and LLM tokens. Every dollar, proven with a live query."
Screen: Mission Control home, savings ticker + findings grid visible. No slides.
(Scale note if asked: this is a tiny demo stack — the same detectors on production volumes find
thousands/month. The point is the *closed loop*, not the demo's $80.)

**0:20–0:50 · Evidence, not claims**
Click finding **T2 (orphan metrics) — $57.96/mo**. Read the safety proof out loud: "seven
metrics, zero dashboards, zero alerts reference them — checked, not guessed." Click one evidence
link → lands in SigNoz Metrics Explorer showing the metric's real volume. Back to Mission Control.
> "Every number here is a live query against SigNoz — the model explains, it never invents."

**0:50–1:40 · Money shot #1 — fix telemetry, verified**
Open the generated patch (YAML with rationale header). Click **Apply** on **T1 (debug-log
flood)**. Cut to browser B: logs volume for `orders` stepping down. Back to A: green banner —
> "Verified: debug-log ingest down 100% — and every dashboard and alert still resolves,
> nothing broke."
> "That's the difference between a script that deletes data and a tool a platform team can
> trust: it proves the leak stopped AND that it broke nothing."
Bonus beat (optional, ~8s): open **T4 (cardinality bomb)** — "a per-user `user_id` label
exploded one metric to thousands of series; the fix drops just that label, keeps the metric."

**1:40–2:20 · Money shot #2 — the AI-era leak**
Open **L1 (cacheable duplicates) — $9.85/mo**: "ten distinct questions, answered fresh 438
times — 428 of those were exact repeats paid for in full." Apply the cache. Verify: cacheable
repeats collapse to zero.
> "Same loop, different domain: infra bytes and AI tokens are the two bills every team pays,
> and nobody audits them together."

**2:20–2:50 · The kicker for this room**
Open Agent Ops dashboard in SigNoz: SpanSaver's own token spend, traced.
> "A cost auditor should disclose its own cost — this audit run cost <MEASURE ¢>. And SigNoz's
> Cost Meter announcement says intelligent cost-optimization recommendations are on their
> roadmap. This is that feature, running today, open source, closed-loop."

**2:50–3:00 · Close**
Judge Mode page on screen (criteria → live links).
> "Detect, prove, fix, verify. SpanSaver — stop paying for data nobody reads."

## Before you record — two setup gaps to close
1. **Integrity story is thin.** The sweep currently protects only **1 dashboard, 0 alerts**, so
   the "nothing broke" line lands weak. Import 2–3 dashboards (incl. `dashboards/agent-ops.json`)
   and add a couple of alert rules in SigNoz first — then the banner reads "N dashboards and M
   alerts intact" with real weight.
2. **Auditor's own cost (2:20 kicker)** — measure it from the Agent Ops dashboard (or the run's
   gen_ai spans) and drop the real figure into `<MEASURE ¢>`.

## Recording plan (Day 4)
- Record each segment separately; keep takes. Assemble once. 1080p, 125% zoom, cursor
  highlighting on.
- Record a full backup run BEFORE any Day-5 code change.
- Live-judging variant: same script, but pre-open all tabs; if anything hangs, narrate over
  the backup recording without apologizing. If ClickHouse falls over (WSL quirk), `docker
  restart` the clickhouse containers — 5s recovery — then continue.
- Rehearse the two transitions (Apply → SigNoz graph) until they're < 5s each; dead air kills
  a 3-minute demo.

## Numbers discipline
The figures above are REAL as of the 2026-07-22 run but drift with data volume. Re-run
`make demo` immediately before recording and reconcile every spoken number with what's on
screen. Veteran judges remember when a spoken number doesn't match the screen.
