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

## Import
SigNoz UI → **Dashboards → + New dashboard → Import JSON** → paste `agent-ops.json` (or upload it).
Then set the time range to cover your traffic window.

> **Time-filter tokens:** panels use SigNoz's clickhouse-query templating
> (`{{.start_datetime}}`, `{{.end_datetime}}`, `{{.step_interval}}`). These are stable on v0.133.
> If this build rejects the import or a panel shows no data, recreate the panel via
> **+ New panel → ClickHouse Query** and paste the query below — the SQL itself is version-proof.

## Raw queries (fallback — build panels by hand if import ever drifts)
Shared filter on every query:
```sql
serviceName = 'askdocs'
AND mapContains(attributes_string, 'gen_ai.input.messages')   -- = a gen_ai/LLM span
AND timestamp BETWEEN {{.start_datetime}} AND {{.end_datetime}}
FROM signoz_traces.distributed_signoz_index_v3
```

**Tokens over time** (two series):
```sql
SELECT toStartOfInterval(timestamp, INTERVAL {{.step_interval}} SECOND) AS ts,
       sum(attributes_number['gen_ai.usage.input_tokens']) AS value
FROM signoz_traces.distributed_signoz_index_v3
WHERE serviceName='askdocs' AND mapContains(attributes_string,'gen_ai.input.messages')
  AND timestamp BETWEEN {{.start_datetime}} AND {{.end_datetime}}
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
  AND timestamp BETWEEN {{.start_datetime}} AND {{.end_datetime}}
GROUP BY prompt_hash HAVING calls >= 2 ORDER BY calls DESC LIMIT 20
```

**Calls & tokens by model (table):** `GROUP BY attributes_string['gen_ai.response.model']` with
`count()` and `sum(...)` of input/output tokens.
