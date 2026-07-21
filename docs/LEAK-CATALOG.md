# SpanSaver — Leak Catalog (the spec)

This file is the source of truth for what SpanSaver detects and fixes. Every detector, patch
generator, and UI card maps to an entry here by ID. Update this file first, code second.

Shared rules:
- **$ math** = measured volume × rate from `.env` (`PRICE_PER_GB_INGEST`,
  `PRICE_IN_PER_MTOK`, `PRICE_OUT_PER_MTOK`), extrapolated to 30 days. Always labeled
  "assumed rate" in the UI. We show the math, we don't hide it.
- **Detection windows** default to last 24h of data (env: `AUDIT_WINDOW_HOURS`).
- Query sketches below are *sketches* — table names and attribute keys must be confirmed
  against the live ClickHouse/SigNoz instance before implementation (see 00-project rule:
  introspect, don't guess).
- **Cut priority** = what we drop first if time runs out (5 = cut first, 1 = never cut).

---

## Domain T — Telemetry waste

### T1 · Debug-log flood
- **What / why common:** DEBUG/TRACE-level logs shipped from a hot path into production
  ingestion. Every team has done this; it's usually the single biggest line item.
- **Signal source:** ClickHouse `signoz_logs` — volume grouped by `service.name` and severity;
  bytes via log body length or `system.parts` for the table overall.
- **Detection sketch:** share of log volume with severity in (DEBUG, TRACE) per service over
  the window; flag services where that share > 30% and absolute size > threshold.
- **Usage cross-check:** query SigNoz saved views/dashboards/alerts for filters referencing
  those services' DEBUG logs. Expected in demo: zero references.
- **$ math:** GB/day of flagged logs × 30 × `PRICE_PER_GB_INGEST`.
- **Fix:** collector patch — filter processor drops logs where severity < INFO for the flagged
  services only (scoped, never global).
- **Safety proof:** "0 dashboards / 0 alerts / 0 saved views reference DEBUG-level logs for
  service X."
- **Verification:** log bytes/min for the service, 10-min before vs after window; all
  dashboards/alerts still resolve (integrity check = re-fetch each, confirm no broken query).
- **Demo seeding:** `WASTE_DEBUG_FLOOD=1` makes orders log a ~1KB DEBUG line per request.
- **Cut priority:** 1 (headline leak).

### T2 · Orphan metrics
- **What / why common:** Custom metrics someone added "temporarily," referenced by no
  dashboard and no alert, ingested forever.
- **Signal source:** metric names + datapoint counts + series cardinality from
  `signoz_metrics` (and Metrics Explorer's own metadata where accessible); dashboard + alert
  definitions from the SigNoz API.
- **Detection sketch:** set difference — ingested metric names minus (metric names appearing
  in any dashboard query or alert rule). Rank by datapoints/day. Exclude `signoz_`-internal
  and runtime/system metrics via an allowlist to avoid false positives.
- **$ math:** datapoints/day share of metrics bill (or bytes where measurable) × rate.
- **Fix:** collector patch — filter processor drop list of exact metric names.
- **Safety proof:** the cross-reference itself, listed per metric: "referenced by: none."
- **Verification:** flagged metric names stop appearing in fresh ingestion; dashboards/alerts
  integrity check passes.
- **Demo seeding:** `WASTE_ORPHAN_METRICS=1` emits 6 plausible-looking never-used counters
  from payments.
- **Cut priority:** 1 (this is the "SigNoz roadmap gap" leak — the differentiator).

### T3 · Health-check span spam
- **What / why common:** `/healthz` probes every 2s × every service × every replica = a giant
  share of trace ingestion that nobody has ever opened.
- **Signal source:** `signoz_traces` — span counts grouped by route/name attribute.
- **Detection sketch:** spans whose route matches health/ready/live patterns AND status OK,
  as a % of total spans; flag when > 20%.
- **$ math:** span bytes share × rate.
- **Fix:** collector patch — filter processor drops spans matching those routes (errors on
  health routes are kept — that's signal).
- **Safety proof:** "0 dashboards/alerts query these routes; error-status health spans are
  excluded from the drop."
- **Verification:** spans/min for those routes → ~0 after apply; total trace volume drop shown.
- **Demo seeding:** `WASTE_HEALTH_SPANS=1` adds aggressive healthcheck loops between services.
- **Cut priority:** 2.

### T4 · Cardinality bomb
- **What / why common:** a per-user / per-request ID lands in a metric attribute; series count
  explodes; the metrics bill follows.
- **Signal source:** series counts per metric (time-series tables in `signoz_metrics`);
  top attributes by distinct values.
- **Detection sketch:** metrics whose active series > threshold with one attribute
  contributing most of the cardinality (distinct-count per attribute key).
- **$ math:** series above the metric's median baseline × datapoint rate × price.
- **Fix:** **not** a label drop. Collector patch uses the metrics transform processor to
  aggregate away the offending attribute (or drops the metric if it's also orphaned).
  Dropping attributes alone does not reduce series/cost — this nuance is called out in the
  UI because it's exactly the mistake experienced judges have seen teams make.
- **Safety proof:** "attribute `user_id` on `checkout_latency` is not used in any dashboard
  group-by or alert filter."
- **Verification:** active series count for the metric, before vs after.
- **Demo seeding:** `WASTE_CARDINALITY=1` adds `user_id` to a payments histogram.
- **Cut priority:** 3 (great story, slightly fiddlier verification).

### T5 · Duplicate instrumentation
- **What:** the same signal ingested twice (e.g., both auto- and manual-instrumented HTTP
  server spans, or the same host metrics from two receivers).
- **Detection sketch:** near-identical span pairs (same trace, same route, same duration ±ε)
  or metric name pairs with correlated values.
- **Fix:** drop one source via collector patch.
- **Cut priority:** 5 (cut first; keep in the catalog as "future work" — honest roadmaps
  impress veterans).

---

## Domain L — LLM token waste

### L1 · Cacheable duplicates
- **What / why common:** the same prompt answered fresh every time. FAQ-style traffic against
  an uncached LLM endpoint is the norm, not the exception.
- **Signal source:** gen_ai spans from askdocs (Traceloop). Confirm real attribute keys for
  prompt/input, model, and token usage on a dumped span; pin as constants.
- **Detection sketch:** normalize + hash prompt text; group by hash over the window; flag
  hashes with count ≥ 5; waste = (count − 1) × avg tokens of that hash.
- **$ math:** wasted input/output tokens × per-Mtok rates.
- **Fix:** enable the response cache in askdocs (env `ASKDOCS_CACHE=1`, exact-match hash
  cache, TTL 1h) — the generated "patch" here is a config change + a diff shown in the UI.
- **Safety proof:** cache is exact-match only + TTL-bounded; no semantic guessing, so no
  wrong-answer risk. State this plainly in the UI.
- **Verification:** tokens/min and $/min panels before vs after; cache hit-rate metric.
- **Demo seeding:** `WASTE_LLM_NOCACHE=1` + traffic generator sends a zipfian distribution of
  ~10 questions (realistic FAQ pattern).
- **Cut priority:** 1 (headline LLM leak; the token graph stepping down is the second money
  shot of the demo).

### L2 · Prompt bloat
- **What:** a huge static preamble (full product docs) glued to every request regardless of
  question.
- **Detection sketch:** input tokens p50/p95 per endpoint; flag when p50 input tokens > 8×
  p50 output tokens AND a large common prefix is detected across prompts (prefix of the
  stored prompt attribute).
- **$ math:** (common-prefix tokens − a 500-token allowance) × request count × input rate.
- **Fix:** generated prompt diff — move static context behind retrieval (askdocs already has
  the RAG path; the wasteful mode bypasses it). Applying = flipping `WASTE_LLM_BLOAT=0`;
  the UI shows the before/after prompt diff.
- **Verification:** p50 input tokens per request, before vs after.
- **Cut priority:** 2.

### L3 · Retry storms
- **What:** naive retry loops multiplying token spend on transient failures.
- **Detection sketch:** ≥3 gen_ai spans with identical prompt hash within 30s in one trace,
  earlier ones ending in error status.
- **Fix:** recommendation card (exponential backoff + circuit breaker snippet). Recommend-only
  is acceptable here — say so honestly in the UI ("fix: suggested, not auto-applied").
- **Cut priority:** 4.

### L4 · Model overkill
- **What:** flagship-tier model answering trivial short lookups.
- **Detection sketch:** spans where model ∈ expensive tier AND input+output tokens < 300 AND
  prompt matches simple-lookup patterns; compare cost vs the cheap-tier rate for the same
  volume.
- **Fix:** routing suggestion with projected savings (recommend-only).
- **Cut priority:** 4.

---

## Finding lifecycle (all IDs)
detected → fix_ready (patch/diff generated + safety proof attached) → applied → verified
(before/after numbers captured) — or → failed with a loud reason. The demo narrates exactly
this lifecycle for T1 or T2 and for L1.
