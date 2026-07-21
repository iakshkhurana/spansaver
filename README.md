# SpanSaver 🔎💸

**Stop paying for data nobody reads.** SpanSaver is an AI auditor for the two bills every
engineering team pays — observability ingestion and LLM tokens. It finds the leaks, proves
they're safe to fix, applies the fix, and verifies the savings against live SigNoz data.

> Built for **Agents of SigNoz** (WeMakeDevs × SigNoz, July 2026) · Track 01

<!-- DEMO GIF: apply → ingestion drops → green "verified, nothing broke" banner -->

## The loop
1. **Detect** — 9 leak types across telemetry (debug floods, orphan metrics, health-span
   spam, cardinality bombs…) and LLM usage (cacheable duplicates, prompt bloat, retry
   storms, model overkill), measured from ClickHouse + SigNoz APIs. Numbers from queries,
   never from the model.
2. **Prove** — every drop candidate is cross-referenced against every SigNoz dashboard and
   alert: *"referenced by: none."* No proof → recommend-only.
3. **Fix** — reviewable OTel Collector patches / config diffs, validated, reversible.
4. **Verify** — before/after ingestion & token graphs plus an integrity sweep confirming all
   dashboards and alerts survived. Green banner or it didn't happen.

Bonus: SpanSaver's own LLM calls are traced into SigNoz — the Agent Ops dashboard discloses
what each audit cost.

## Quickstart
See [docs/SETUP.md](docs/SETUP.md). Short version: self-host SigNoz, `cp .env.example .env`,
`make up && make waste-on && make traffic`, wait 10 minutes, `make audit`, open Mission
Control, click Apply, watch the graphs.

## For judges
[docs/JUDGING-MAP.md](docs/JUDGING-MAP.md) maps all six criteria to live evidence — also
served at `/judge` in the app. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
What it detects and why it's safe: [docs/LEAK-CATALOG.md](docs/LEAK-CATALOG.md).
Honest limitations: [docs/PITCH.md](docs/PITCH.md#qa-bank).

## Built with
SigNoz (self-host) · OpenTelemetry Collector (filter/transform, OTTL) · ClickHouse ·
Traceloop (OpenLLMetry) · FastAPI · Next.js · and SigNoz's MCP server in our editor while
building it.

## Team
<!-- names / handles -->

*Prices shown are configurable assumptions (`.env`) and labeled as such in the UI.*
