# Pitch & Q&A

## One-liner
**SpanSaver finds the money leaking from your stack — telemetry nobody reads and tokens nobody
needed — then proves it's safe to fix, fixes it, and verifies the savings.**

## Problem (discovery framing)
- **What problem exists?** Teams pay for observability data that no dashboard or alert ever
  uses, and for LLM tokens burned on duplicate/bloated/misrouted calls. Both are invisible by
  default: cost tools show totals, not *waste*.
- **Who experiences it?** Every team running production observability, and now every team
  shipping AI features. Both bills, same engineers.
- **How do they handle it today?** Quarterly panic audits, hand-written OTel filter rules
  from blog posts, spreadsheet archaeology on the invoice, or nothing. LLM-side: a cost graph
  in a separate tool, with no link to infra.
- **What's the impact if unsolved?** Five-to-six-figure annual overspend at modest scale,
  plus signal buried in noise — waste doesn't just cost money, it slows debugging.
- **Why now?** AI workloads made telemetry AND token spend explode simultaneously, and
  OpenTelemetry gen_ai conventions finally put both on the same wire. The audit is possible
  now in a way it wasn't two years ago.

## Solution
- **Target users:** platform/SRE engineers who own the observability bill; AI feature teams
  who own the token bill. Usually the same on-call rotation.
- **Key capabilities:** detect (9 leak types across 2 domains) → prove safety
  (cross-reference every dashboard/alert) → generate the fix (reviewable OTel patches /
  config diffs) → apply (hot-reload, reversible) → verify (before/after + integrity sweep).
- **What makes it different:** the loop is closed and the proof is mandatory. Nothing gets
  dropped without evidence that nothing depends on it, and nothing counts as fixed until the
  graphs confirm it.

## Success metrics (what we measure on our own demo)
$/month identified · $/month verified-recovered · % ingestion reduced with 0 broken
dashboards/alerts · token cost reduction after cache · auditor's own cost per run (disclosed).

## Q&A bank — rehearse these out loud

**"How is this different from Cribl / Mezmo / telemetry pipeline products?"**
Those are enterprise pipeline platforms: powerful routing/reduction, closed-source, priced
for large orgs, and blind to LLM economics. SpanSaver is open, runs on the OTel Collector you
already have, adds the *usage cross-reference* (is this data actually consumed in SigNoz?)
as a first-class safety proof, and treats token waste as the same problem — because to the
team paying both bills, it is.

**"Grafana has Adaptive Metrics. Datadog meters usage."**
Adaptive Metrics is metrics-only inside Grafana Cloud; Datadog shows you usage but the
optimization stays manual and the platform is closed. Neither touches tokens; neither closes
the loop with verified apply on open infrastructure.

**"Doesn't SigNoz already do this with Cost Meter / Metrics Explorer?"**
SigNoz gives excellent *visibility* — Cost Meter for ingestion, Metrics Explorer for
high-volume and unused metrics — and their own launch post says intelligent optimization
recommendations are the planned next step. SpanSaver is that next step, built on top of those
features, plus the safety proof, the apply, the verification, and the LLM domain. We built
the roadmap item, and we'd love to upstream it.

**"Langfuse / Helicone already track LLM cost."**
They report spend. SpanSaver finds *leaks* — duplicates, bloat, retries, overkill — quantifies
each, applies the cache fix, and verifies the drop, in the same pane as your infra waste.
Reporting vs. auditing.

**"Is auto-dropping telemetry safe?"**
We never drop on model opinion. A drop requires the cross-reference proof (zero dashboards,
zero alerts, zero saved views), patches are scoped and reversible, the merged config is
validated before reload, and the verification sweep re-checks every dashboard and alert
afterward. Where proof isn't possible (retry storms, model routing), we recommend instead of
apply — and the UI says so.

**"What are the limitations?"** (answer before they ask — veterans reward this)
Prices are configurable assumptions, clearly labeled. ClickHouse-direct queries couple us to
self-host — on SigNoz Cloud we'd read the meter metrics instead. Detectors are transparent
heuristics with thresholds, not ML — for an auditor, explainable beats clever. T5 and parts
of L3/L4 are recommend-only today; that's the honest roadmap.

**"Why should the AI part be trusted?"**
It isn't trusted with numbers. Volumes, counts, and costs come from queries; the model ranks,
explains, and drafts configs that are validated before use. And its own usage is traced in
SigNoz — the Agent Ops dashboard shows what this audit cost, to the cent.
