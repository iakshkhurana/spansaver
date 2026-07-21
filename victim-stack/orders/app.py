"""orders — a deliberately ordinary FastAPI service.

Emits normal business traces + INFO logs. When WASTE_DEBUG_FLOOD=1 it also ships a ~1KB
DEBUG line per request — the T1 "debug-log flood" leak the auditor detects and drops.
Instrumentation is auto: the container runs under `opentelemetry-instrument`, so FastAPI
spans and the stdlib logging bridge are wired up without touching this file.
"""
import json
import logging
import os
import random
import uuid

from fastapi import FastAPI

WASTE_DEBUG_FLOOD = os.getenv("WASTE_DEBUG_FLOOD", "0") == "1"

# DEBUG level only matters when the flood is armed; otherwise stay at INFO so the junk
# lines are never even generated.
logging.basicConfig(
    level=logging.DEBUG if WASTE_DEBUG_FLOOD else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("orders")

app = FastAPI(title="orders")

PRODUCTS = ["widget", "sprocket", "gadget", "gizmo", "cog", "flange"]
REGIONS = ["us-east", "us-west", "eu-central", "ap-south"]
_recent: list[dict] = []


def _debug_blob(order: dict) -> str:
    """~1KB of plausible-looking DEBUG noise: the kind of full-object dump teams leave in
    a hot path and forget. Padded so each flood line is roughly 1KB (see LEAK-CATALOG T1)."""
    payload = {
        "event": "order.trace",
        "order": order,
        "headers": {
            "user-agent": "checkout-web/4.12.0 (+https://example.test)",
            "x-request-id": uuid.uuid4().hex,
            "x-session": uuid.uuid4().hex,
            "accept-encoding": "gzip, deflate, br",
        },
        "cache_keys": [f"order:{order['id']}:{i}" for i in range(6)],
        "feature_flags": {f"flag_{i}": bool(random.getrandbits(1)) for i in range(12)},
        "notes": "internal debug dump; safe to drop; nobody reads this in prod ",
    }
    blob = json.dumps(payload)
    if len(blob) < 1024:
        blob += "x" * (1024 - len(blob))
    return blob


@app.get("/")
def root():
    return {"service": "orders", "waste_debug_flood": WASTE_DEBUG_FLOOD}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/orders")
def create_order():
    order = {
        "id": uuid.uuid4().hex[:12],
        "product": random.choice(PRODUCTS),
        "qty": random.randint(1, 5),
        "region": random.choice(REGIONS),
        "total": round(random.uniform(5, 500), 2),
    }
    _recent.append(order)
    del _recent[:-50]
    log.info("order created id=%s product=%s total=%.2f", order["id"], order["product"], order["total"])
    if WASTE_DEBUG_FLOOD:
        log.debug("order debug dump %s", _debug_blob(order))
    return order


@app.get("/orders")
def list_orders():
    return {"count": len(_recent), "orders": _recent[-10:]}
