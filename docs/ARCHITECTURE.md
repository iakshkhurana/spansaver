# SpanSaver — Architecture

## Components

```
                       ┌────────────────────────────────────────────┐
                       │                 SigNoz (self-host)         │
                       │  UI · API · ClickHouse · alerts · MCP      │
                       └───────▲───────────────────▲────────────────┘
                     OTLP      │                   │  read: API + ClickHouse
              ┌────────────────┴──────┐    ┌───────┴────────────────┐
              │   OTel Collector      │    │   Auditor (FastAPI)    │
              │ baseline + patches/   │◄───┤ detectors · fixgen ·   │
              │ (reloadable)          │apply│ verifier · SSE        │
              └───────▲───────────────┘    └───────▲────────────────┘
        OTLP          │                            │ REST + SSE
   ┌──────────────────┴─────────────┐      ┌───────┴────────────────┐
   │ victim-stack                   │      │ Mission Control (Next) │
   │ orders · payments · askdocs(LLM)│      │  /  /leak/[id]  /judge │
   └────────────────────────────────┘      └────────────────────────┘
```

## Data flow (one full loop)
1. **Ingest** — victim services emit traces/metrics/logs via OTLP → our collector → SigNoz.
   askdocs LLM calls are instrumented with Traceloop, so token usage rides on spans.
   The collector also scrapes node_exporter via its Prometheus receiver (migration story).
2. **Detect** — `POST /audit`: detectors query ClickHouse (volumes, cardinality, span/token
   stats) and the SigNoz API (dashboard + alert definitions) and emit `Finding`s.
3. **Prove** — for each drop candidate, the cross-reference against every dashboard query and
   alert rule becomes the `safety_proof`. No proof → the fix stays "recommend-only."
4. **Fix** — fixgen writes a patch file under `collector/patches/` (or a config diff for LLM
   leaks) and attaches it to the finding.
5. **Apply** — merges baseline + applied patches, validates the merged config, hot-reloads
   the collector. Reversible by removing the patch and reloading.
6. **Verify** — verifier captures a before window, waits, captures after: bytes/min,
   spans/min, series count, tokens/min as relevant — plus an integrity sweep that re-fetches
   every dashboard and alert to confirm none broke. Result lands on the finding and the UI
   flips to the green verified banner.

## Decisions worth defending to judges
- **Collector-in-the-path**: fixes apply at the pipeline, not in app code — that's how a real
  platform team would do it, and it makes apply/revert instant and safe.
- **ClickHouse direct for volumes**: ingestion size/cardinality questions are storage
  questions; asking the storage engine is more honest than sampling. (On SigNoz Cloud we'd
  use the meter metrics instead — say this when asked about portability.)
- **Patches as reviewable files**: judges can `cat` the generated YAML with its rationale
  header. Auditable > magical.
- **LLM as explainer, not oracle**: models rank findings and draft configs; all numbers come
  from queries. This one sentence defuses the "AI made it up" objection.
- **The auditor audits itself**: its own LLM calls are Traceloop-instrumented into SigNoz;
  the Agent Ops dashboard shows what SpanSaver itself spends. Cost tool that discloses its own
  cost = instant credibility.

## Failure modes → fallbacks
- Collector reload breaks → config is validated pre-reload; last-known-good baseline restore
  is one make target.
- SigNoz API routes differ on the installed version → routes are discovered once, pinned as
  constants; if discovery fails, findings still render with "usage check unavailable" and
  fixes become recommend-only (degrade, don't die).
- ClickHouse table names differ → startup introspection maps logical names → real tables;
  missing table disables that detector with a visible warning.
- Live demo risk → `make demo` runs against pre-seeded data; backup screen recording of every
  segment exists from Day 4.
