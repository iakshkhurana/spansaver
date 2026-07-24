# SigNoz dashboards

JSON to import into your self-hosted SigNoz (v0.133). Every panel query uses **confirmed** names:
`signoz_index_v3` columns (auditor/telemetry_auditor/schema.py) and the pinned gen_ai attribute
keys (auditor/llm_auditor/attrs.py). No guessed schema.

## agent-ops.json — SpanSaver · Agent Ops
LLM/agent observability for `askdocs`, mined from gen_ai spans (Traceloop/OpenLLMetry). It shows
the exact signals the L1/L2 detectors act on, so the dashboard and the auditor tell the same story:

| Panel | Shows | Ties to |
|-------|-------|---------|
| LLM tokens over time | input vs output tokens / interval | L1 (steps down on cache) |
| LLM calls / interval | gen_ai span count | L1 (cache hits emit no span) |
| Input tokens p50 / p95 | prompt-size distribution | L2 (bloat = high p50) |
| Cache-read input tokens | `gen_ai.usage.cache_read.input_tokens` | L1 (cache doing work) |
| Total tokens (window) | sum in/out over range | headline number |
| Calls & tokens by model | per-model cost drivers | model overkill (L4, future) |
| Cacheable duplicate prompts | prompt hashes seen >1× | L1 evidence |

## telemetry-cost.json — SpanSaver · Telemetry Cost
Infra-side observability waste for the victim stack — the signals the T1/T3/T4 detectors act on,
so the dashboard and the auditor tell the same story. Confirmed columns only (schema.py):

| Panel | Shows | Ties to |
|-------|-------|---------|
| Total log bytes (window) | `sum(length(body))` across services | T1 headline |
| Log volume by service | bytes · DEBUG lines · total lines / service | T1 (debug flood = high DEBUG share) |
| DEBUG vs INFO+ over time | severity 1-8 vs 9+ per minute | T1 (DEBUG steps to ~0 after apply) |
| Spans by route | span + error count per `httpRoute` | T3 (probe spam, 0 errors) |
| Active series per metric | `uniqExact(fingerprint)` per `metric_name` | T4 (cardinality bomb) |

> Note the two time bases: `logs_v2.timestamp` is **UInt64 nanoseconds** (`{{.start_timestamp_ms}} * 1000000`),
> `signoz_index_v3.timestamp` is **DateTime64** (`fromUnixTimestamp64Milli(...)`), and
> `time_series_v4.unix_milli` is **epoch millis** (`{{.start_timestamp_ms}}` directly).

## Import
SigNoz UI → **Dashboards → + New dashboard → Import JSON** → paste `agent-ops.json` **and**
`telemetry-cost.json` (import both — the verify integrity sweep counts every dashboard that still
resolves, so more imported dashboards = a stronger "N dashboards intact" banner). Set the time
range to cover your traffic window.

> **Time-filter tokens (confirmed on v0.133):** panels use `{{.start_timestamp_ms}}` /
> `{{.end_timestamp_ms}}` (epoch millis, via `fromUnixTimestamp64Milli`). Bucketing is a fixed
> `INTERVAL 1 MINUTE` — this build does **not** expand `{{.step_interval}}` (it passes through
> literally and breaks the query). If a panel shows no data, recreate it via
> **+ New panel → ClickHouse Query** and paste the query below — the SQL is version-proof.

## Raw queries (fallback — build panels by hand if import ever drifts)
Shared filter on every query:
```sql
serviceName = 'askdocs'
AND mapContains(attributes_string, 'gen_ai.input.messages')   -- = a gen_ai/LLM span
AND timestamp >= fromUnixTimestamp64Milli({{.start_timestamp_ms}})
  AND timestamp <= fromUnixTimestamp64Milli({{.end_timestamp_ms}})
FROM signoz_traces.distributed_signoz_index_v3
```

**Tokens over time** (two series):
```sql
SELECT toStartOfInterval(timestamp, INTERVAL 1 MINUTE) AS ts,
       sum(attributes_number['gen_ai.usage.input_tokens']) AS value
FROM signoz_traces.distributed_signoz_index_v3
WHERE serviceName='askdocs' AND mapContains(attributes_string,'gen_ai.input.messages')
  AND timestamp >= fromUnixTimestamp64Milli({{.start_timestamp_ms}})
  AND timestamp <= fromUnixTimestamp64Milli({{.end_timestamp_ms}})
GROUP BY ts ORDER BY ts
-- second series: swap input_tokens -> output_tokens
```

**LLM calls / interval:** `count() AS value` with the same GROUP BY ts.

**Input tokens p50 / p95:** `quantile(0.5)(attributes_number['gen_ai.usage.input_tokens'])`
(and `quantile(0.95)(...)`) with GROUP BY ts.

**Cache-read tokens:** `sum(attributes_number['gen_ai.usage.cache_read.input_tokens']) AS value`.

**Cacheable duplicate prompts (table):**
```sql
SELECT cityHash64(attributes_string['gen_ai.input.messages']) AS prompt_hash,
       count() AS calls, count()-1 AS repeats,
       round(avg(attributes_number['gen_ai.usage.input_tokens']))  AS avg_input_tokens,
       round(avg(attributes_number['gen_ai.usage.output_tokens'])) AS avg_output_tokens
FROM signoz_traces.distributed_signoz_index_v3
WHERE serviceName='askdocs' AND mapContains(attributes_string,'gen_ai.input.messages')
  AND timestamp >= fromUnixTimestamp64Milli({{.start_timestamp_ms}})
  AND timestamp <= fromUnixTimestamp64Milli({{.end_timestamp_ms}})
GROUP BY prompt_hash HAVING calls >= 2 ORDER BY calls DESC LIMIT 20
```

**Calls & tokens by model (table):** `GROUP BY attributes_string['gen_ai.response.model']` with
`count()` and `sum(...)` of input/output tokens.
