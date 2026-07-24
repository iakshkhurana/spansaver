# SigNoz alert rules — the "nothing broke" weight

The verify integrity sweep (`auditor/verifier/verify.py` → `integrity_sweep`) re-fetches every
alert rule via `GET /api/v1/rules` and counts how many still resolve. **More real alert rules =
a heavier green banner** ("N dashboards and **M alerts** intact"). With zero alerts the banner
reads "0 alerts" and the safety story lands weak.

None of these alerts reference DEBUG logs, health-probe spans, orphan metrics, or the dropped
cardinality label — so **every SpanSaver fix leaves them resolving**, which is exactly the point:
the drop stops waste and breaks nothing you rely on.

> **Why a recipe, not an import JSON:** the alert-rule JSON shape is version-specific and *not*
> yet confirmed on this SigNoz build (golden rule #1 — introspect, don't guess; the `/api/v1/rules`
> route is confirmed, the POST body schema is not). Create these three in the UI from the confirmed
> ClickHouse queries below; each takes ~30s. Dump a created rule with
> `python -m auditor.telemetry_auditor.signoz_api rules` to pin the real schema later if you want
> importable JSON.

## Create in the UI
SigNoz → **Alerts → New Alert → ClickHouse Query**. Paste the query, set the threshold, name it,
save. Use a short evaluation window (e.g. last 5 min) so it's live during the demo.

### 1 · askdocs LLM spend spike  *(AI observability — the track signal)*
Fires if askdocs burns more than an expected number of tokens in 5 minutes.
```sql
SELECT sum(attributes_number['gen_ai.usage.input_tokens'] + attributes_number['gen_ai.usage.output_tokens']) AS value
FROM signoz_traces.distributed_signoz_index_v3
WHERE serviceName = 'askdocs'
  AND mapContains(attributes_string, 'gen_ai.input.messages')
  AND timestamp >= now() - INTERVAL 5 MINUTE
```
Condition: `value > 200000` (tune to your traffic). Note: after the L1 cache fix this *drops* —
the alert keeps resolving, it just trends down. It protects against a runaway-cost regression.

### 2 · orders error rate
Fires if the `orders` service starts erroring. Uses the flattened `has_error` column.
```sql
SELECT countIf(has_error) AS value
FROM signoz_traces.distributed_signoz_index_v3
WHERE serviceName = 'orders'
  AND timestamp >= now() - INTERVAL 5 MINUTE
```
Condition: `value > 0` (or a small tolerance). T1 drops only DEBUG *logs* — error *spans* are
untouched, so this alert is unaffected by the fix.

### 3 · payments latency (p95)
Fires if p95 span duration for `payments` regresses. `duration_nano` → ms.
```sql
SELECT quantile(0.95)(duration_nano) / 1e6 AS value
FROM signoz_traces.distributed_signoz_index_v3
WHERE serviceName = 'payments'
  AND timestamp >= now() - INTERVAL 5 MINUTE
```
Condition: `value > 800` (ms; tune to your stack).

## Verify the sweep sees them
```bash
python -m auditor.telemetry_auditor.signoz_api rules   # should list the 3 rules
make verify F=T1                                        # banner: "N dashboards and 3 alerts intact"
```
