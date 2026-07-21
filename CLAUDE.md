# CLAUDE.md — SpanSaver

## What this is
SpanSaver is a hackathon project (Agents of SigNoz, deadline **July 26, 2026**) — an AI auditor
that finds money leaking from an engineering stack in two domains and fixes it safely:

1. **Telemetry waste** — logs/metrics/spans ingested into SigNoz that no dashboard or alert
   ever uses (debug-log floods, orphan metrics, health-check span spam, cardinality bombs).
2. **LLM token waste** — mined from gen_ai trace spans: cacheable duplicate prompts,
   prompt bloat, retry storms, expensive models on trivial tasks.

The loop: **Detect → Prove safety → Generate fix → Apply → Verify with real metrics.**
The "prove safety" and "verify" steps are the product. Never skip them, never fake them.

Team = 1 human + Claude. Judges are 30+ yr US engineers. Working demo > elegant code.

## Golden rules (non-negotiable)
1. **Introspect, don't guess.** SigNoz API routes, ClickHouse table names, and gen_ai span
   attribute keys vary by version. Before writing a query: `SHOW TABLES` / `DESCRIBE`, hit the
   API and read the real response, or dump one real span's attributes. Never invent a schema.
2. **No fake data in the product.** Every number in the UI comes from a real query. The only
   assumptions allowed are pricing rates, which live in `.env` and are labeled "assumed rate"
   in the UI. Mock data may exist only behind `?demo=mock` and never in the demo video.
3. **Every finding carries evidence.** A leak without a working deep-link into SigNoz
   (Metrics Explorer / trace view / logs view) is not done.
4. **Patches are files, not edits.** Generated collector fixes go to `collector/patches/*.yaml`
   with a header comment (finding id, generated timestamp). Never mutate
   `collector/otel-collector.baseline.yaml` at runtime.
5. **Config via env.** No hardcoded URLs, keys, ports, or prices. See `.env.example`.
6. **Late-sprint discipline.** From July 24 onward: small diffs only, no refactors of working
   code, no new dependencies without asking the human.
7. **Fail loud.** If SigNoz/ClickHouse is unreachable or a query errors, surface a clear
   actionable message in the UI and logs. Silent empty states cost us demo time.

## Repo map
```
collector/        OTel Collector baseline + generated patches (merged at runtime)
victim-stack/     3 deliberately wasteful demo services (orders, payments, askdocs=LLM/RAG)
auditor/          FastAPI brain: telemetry_auditor/, llm_auditor/, fixgen/, verifier/
ui/               Mission Control (Next.js) — report, leak detail, /judge page
dashboards/       SigNoz dashboard JSON to import (incl. Agent Ops)
scripts/          traffic generator, waste seeding, helpers
docs/             THE SPEC. Read docs/LEAK-CATALOG.md before touching auditor code.
```
Data flow: victim-stack → OTel Collector → SigNoz. Auditor reads SigNoz API + ClickHouse,
emits Findings over SSE to the UI, writes patches, triggers collector reload, verifies.

## Commands
```
make up          # victim stack + collector + auditor + ui (SigNoz runs separately)
make waste-on    # enable all WASTE_* toggles and restart victim services
make traffic     # load generator (keep running in background during dev)
make audit       # run full audit, print findings table
make apply F=T2  # apply the generated patch for finding T2, reload collector
make verify F=T2 # before/after volumes + dashboard/alert integrity check
make demo        # seeded end-to-end run for rehearsal
```
SigNoz itself: installed separately via the official self-host Docker install
(see docs/SETUP.md). Set `SIGNOZ_UI_URL` / `SIGNOZ_API_URL` after install — do not assume ports.

## Environment (see .env.example for the full list)
`SIGNOZ_API_URL`, `SIGNOZ_API_KEY`, `SIGNOZ_UI_URL`, `CLICKHOUSE_DSN`,
`LLM_PROVIDER` + key, `PRICE_PER_GB_INGEST`, `PRICE_IN_PER_MTOK`, `PRICE_OUT_PER_MTOK`,
`WASTE_DEBUG_FLOOD`, `WASTE_ORPHAN_METRICS`, `WASTE_HEALTH_SPANS`, `WASTE_CARDINALITY`,
`WASTE_LLM_NOCACHE`, `WASTE_LLM_BLOAT`.

## SigNoz integration notes
- Auth: SigNoz API key in header. Endpoints for dashboards/alert rules exist but differ across
  versions — discover them (browser devtools on the SigNoz UI is fastest) and record the
  confirmed routes in `auditor/telemetry_auditor/signoz_api.py` as constants with a comment.
- ClickHouse: reachable inside SigNoz's docker network (service name usually `clickhouse`).
  Databases of interest: `signoz_logs`, `signoz_traces`, `signoz_metrics`. Table names are
  version-dependent — introspect first. Volume/size via `system.parts` and `system.tables`.
- LLM spans: instrumented via Traceloop (OpenLLMetry). Attribute keys may be `gen_ai.*` or
  legacy `llm.*` — dump one real span and pin the keys as constants before writing detectors.
- The SigNoz MCP server is connected to this editor for dev: use it to sanity-check what data
  exists before writing detector queries.

## Definition of done (any feature)
Runs via a make target + visible in the UI or in SigNoz + one line added to README + human
has seen it work once.

## Current priorities
See `docs/PLAN.md`. If unsure what to build next, build the thing the 3-minute demo
(docs/DEMO-SCRIPT.md) needs and is currently missing.

## Git workflow
- Work in small, self-contained increments (~15–30 min each). One increment = one commit.
- NEVER run git commands yourself. After every increment: stop, list the files you changed, give a 2-line summary of what and why, then output ONE ready-to-copy commit message. I commit and push manually.
- Commit format: Conventional Commits — type(scope): subject. type ∈ feat|fix|docs|chore|refactor|test|perf; scope ∈ collector|orders|payments|askdocs|auditor|ui|docs|scripts|infra. Subject ≤72 chars, imperative, specific — "feat(orders): add OTel auto-instrumentation + WASTE_DEBUG_FLOOD toggle", never "update files". Add a 1–3 line body when the why isn't obvious.
- Cadence target: 15–20 real commits/day (~85 total by Jul 26). Hit it by keeping increments genuinely small — one service, one detector, one endpoint, one doc at a time. Never propose empty or artificially split commits; granularity must be real.
- Remind me to git push after every 3–4 commits and at every DoD checkpoint.
- When a make target or a day's DoD passes, announce it: "DoD CHECK: ..."
