# Judging Map — 6 criteria → what we show

This table is mirrored live on the `/judge` page of Mission Control. Fill the Link column on
Day 4 with real URLs (SigNoz deep links, repo files, dashboard names).

| # | Criterion | What we show | Where (fill Day 4) |
|---|-----------|--------------|--------------------|
| 1 | Potential Impact | Real $/month recovered on a live stack across the two universal bills (telemetry + tokens); savings ticker; the SigNoz Cost Meter roadmap gap we fill | Mission Control home · PITCH.md |
| 2 | Creativity & Innovation | First closed-loop auditor spanning infra telemetry AND LLM tokens; safety-proof step; the tool audits its own AI cost | /leak/T2 safety proof · Agent Ops dashboard |
| 3 | Technical Excellence | ClickHouse introspection, OTTL patch generation with validation + rollback, cardinality handled correctly (aggregate, not label-drop), SSE live UI | collector/patches/ · auditor/ code tour |
| 4 | Best Use of SigNoz | Reads: ClickHouse, dashboards API, alerts API, Metrics Explorer concepts, meter/ingestion data. Writes: dashboards, patches upstream of SigNoz. Plus SigNoz MCP used during development | SpanSaver dashboards in SigNoz · SETUP.md §4 |
| 5 | User Experience | One-screen leak report, evidence deep-links, one-tap Apply, unmissable verified banner, Judge Mode itself | Mission Control walkthrough |
| 6 | Presentation Quality | 3:00 demo where every claim is clicked, not asserted; README quickstart reproduces the loop in <15 min; honest limitations section | Demo video · README |

## The one-liner per criterion (memorize)
1. "It finds real dollars, today, in the two bills every team pays."
2. "Nobody closes the loop across both domains — and our loop includes proof."
3. "It fixes the pipeline the way a platform team would: reviewable patches, validated, reversible."
4. "SigNoz is both our data source and our verification instrument."
5. "Every finding is two clicks: see the evidence, apply the fix."
6. "Three minutes, zero slides, every number live."
