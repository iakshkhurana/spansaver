"""payments — FastAPI service carrying three telemetry-waste toggles.

  WASTE_ORPHAN_METRICS=1  emits 6 plausible-but-never-referenced counters      (leak T2)
  WASTE_HEALTH_SPANS=1    hammers /healthz across services in a background loop (leak T3)
  WASTE_CARDINALITY=1     tags a latency histogram with per-request user_id     (leak T4)

Traces/metrics/logs are auto-exported via `opentelemetry-instrument` (see Dockerfile).
"""
import asyncio
import logging
import os
import random
import uuid

import httpx
from fastapi import FastAPI
from opentelemetry import metrics

WASTE_ORPHAN_METRICS = os.getenv("WASTE_ORPHAN_METRICS", "0") == "1"
WASTE_HEALTH_SPANS = os.getenv("WASTE_HEALTH_SPANS", "0") == "1"
WASTE_CARDINALITY = os.getenv("WASTE_CARDINALITY", "0") == "1"

# Internal service names on the shared docker network; override via env if needed.
HEALTH_TARGETS = os.getenv(
    "HEALTH_CHECK_TARGETS",
    "http://orders:8000/healthz,http://askdocs:8000/healthz,http://payments:8000/healthz",
).split(",")
HEALTH_INTERVAL = float(os.getenv("HEALTH_CHECK_INTERVAL", "1.0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("payments")

meter = metrics.get_meter("payments")

# T2: six counters that look like real business metrics but no dashboard/alert will ever
# reference them. Emitted only when armed so a clean baseline has none.
ORPHAN_METRIC_NAMES = [
    "payments_legacy_retry_total",
    "payments_shadow_ledger_writes_total",
    "payments_fraud_score_recompute_total",
    "payments_settlement_batch_v1_total",
    "payments_currency_reconvert_total",
    "payments_deprecated_webhook_total",
]
_orphans = (
    [meter.create_counter(n, description="temporary; unused") for n in ORPHAN_METRIC_NAMES]
    if WASTE_ORPHAN_METRICS
    else []
)

# T4: a legitimate latency histogram. With low-cardinality attrs it's cheap; adding
# user_id per request explodes active series (the actual cost driver).
checkout_latency = meter.create_histogram("checkout_latency_ms", unit="ms", description="charge latency")

REGIONS = ["us-east", "us-west", "eu-central", "ap-south"]
app = FastAPI(title="payments")


@app.get("/")
def root():
    return {
        "service": "payments",
        "waste": {
            "orphan_metrics": WASTE_ORPHAN_METRICS,
            "health_spans": WASTE_HEALTH_SPANS,
            "cardinality": WASTE_CARDINALITY,
        },
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/charge")
def charge():
    latency = random.uniform(20, 300)
    region = random.choice(REGIONS)
    attrs = {"region": region, "status": "ok"}
    if WASTE_CARDINALITY:
        # per-request id → unbounded series on this histogram (leak T4)
        attrs["user_id"] = uuid.uuid4().hex
    checkout_latency.record(latency, attrs)

    for counter in _orphans:
        counter.add(1, {"region": region})

    charge_id = uuid.uuid4().hex[:12]
    log.info("charge settled id=%s region=%s latency=%.1fms", charge_id, region, latency)
    return {"id": charge_id, "region": region, "latency_ms": round(latency, 1)}


async def _health_loop():
    """Aggressively poll health routes to inflate trace ingestion with spans nobody reads."""
    async with httpx.AsyncClient(timeout=2.0) as client:
        while True:
            for target in HEALTH_TARGETS:
                try:
                    await client.get(target.strip())
                except Exception:  # noqa: BLE001 - health spam must never crash the loop
                    pass
            await asyncio.sleep(HEALTH_INTERVAL)


@app.on_event("startup")
async def _startup():
    if WASTE_HEALTH_SPANS:
        log.info("health-span spam armed: %s every %.1fs", HEALTH_TARGETS, HEALTH_INTERVAL)
        asyncio.create_task(_health_loop())
