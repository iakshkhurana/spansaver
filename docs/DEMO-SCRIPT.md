# Demo Script — 3:00, shot by shot

Layout: browser A = Mission Control, browser B = SigNoz. Pre-seeded via `make demo`
(waste on, ≥24h of data or accelerated equivalent, audit already run once so findings are
warm — we re-run live for authenticity).

**0:00–0:20 · The hook (say the dollar number in the first sentence)**
> "This stack is leaking $1,340 a month and no dashboard will ever tell you. SpanSaver found
> it in 40 seconds — and it can prove every dollar."
Screen: Mission Control home, savings ticker + findings grid visible. No slides.

**0:20–0:50 · Evidence, not claims**
Click finding **T2 (orphan metrics)**. Read the safety proof out loud: "six metrics, zero
dashboards, zero alerts reference them." Click one evidence link → lands in SigNoz showing
the metric's real volume. Back to Mission Control.
> "Every number here is a live query against SigNoz — the model explains, it never invents."

**0:50–1:40 · Money shot #1 — fix telemetry, verified**
Open the generated patch (YAML with rationale header). Click **Apply**. Cut to browser B:
ingestion panel stepping down. Back to A: green banner —
> "Verified: 14 dashboards and 6 alerts intact. Ingestion down 58%."
> "That's the difference between a script that deletes data and a tool a platform team can
> trust: it proves nothing broke."

**1:40–2:20 · Money shot #2 — the AI-era leak**
Open **L1 (cacheable duplicates)**: "the same 10 questions, answered fresh 4,000 times."
Apply the cache. Token-cost panel steps down; cache hit-rate climbs.
> "Same loop, different domain: infra bytes and AI tokens are the two bills every team pays,
> and nobody audits them together."

**2:20–2:50 · The kicker for this room**
Open Agent Ops dashboard in SigNoz: SpanSaver's own token spend, traced.
> "A cost auditor should disclose its own cost — this run cost 11 cents. And SigNoz's Cost
> Meter announcement says intelligent cost-optimization recommendations are on their roadmap.
> This is that feature, running today, open source, closed-loop."

**2:50–3:00 · Close**
Judge Mode page on screen (6 criteria → 6 live links).
> "Detect, prove, fix, verify. SpanSaver — stop paying for data nobody reads."

## Recording plan (Day 4)
- Record each segment separately; keep takes. Assemble once. 1080p, 125% zoom, cursor
  highlighting on.
- Record a full backup run BEFORE any Day-5 code change.
- Live-judging variant: same script, but pre-open all tabs; if anything hangs, narrate over
  the backup recording without apologizing.
- Rehearse the two transitions (Apply → SigNoz graph) until they're < 5s each; dead air kills
  a 3-minute demo.

## Numbers discipline
The $ figures above are placeholders — before recording, replace every number in this script
with the real measured ones and re-read it. Veteran judges remember when a spoken number
doesn't match the screen.
