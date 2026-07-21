#!/usr/bin/env python3
"""Traffic generator for the victim stack.

- orders / payments: steady POST load so telemetry volumes are meaningful.
- askdocs: a ZIPFIAN sample of ~10 FAQ questions, so a handful dominate — realistic FAQ
  traffic and exactly what surfaces the L1 "cacheable duplicates" leak.

askdocs calls spend real LLM tokens, so they're throttled (ASK_EVERY) and can be turned off
(ASKDOCS_LOAD=0). Stdlib only — no pip install needed to run this.

Env:
  ORDERS_URL / PAYMENTS_URL / ASKDOCS_URL   host-published service URLs
  TRAFFIC_INTERVAL   seconds between iterations (default 1.0)
  ASK_EVERY          hit askdocs once per N iterations (default 5)
  ASKDOCS_LOAD       "0" to skip askdocs entirely (default "1")
"""
import json
import os
import random
import time
import urllib.error
import urllib.request

ORDERS_URL = os.getenv("ORDERS_URL", "http://localhost:8001")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://localhost:8002")
ASKDOCS_URL = os.getenv("ASKDOCS_URL", "http://localhost:8003")
ASKDOCS_LOAD = os.getenv("ASKDOCS_LOAD", "1") == "1"
ASK_EVERY = int(os.getenv("ASK_EVERY", "5"))
INTERVAL = float(os.getenv("TRAFFIC_INTERVAL", "1.0"))

# Ordered most-common first; zipf weights make the top few dominate the distribution.
QUESTIONS = [
    "How long does shipping take?",
    "What is your return policy?",
    "What payment methods do you accept?",
    "Do your products have a warranty?",
    "How do I reset my password?",
    "What are your support hours?",
    "Can I get express delivery?",
    "How do I export my account data?",
    "Will my charge show a different name on my statement?",
    "Are returns free?",
]
_WEIGHTS = [1.0 / (i + 1) for i in range(len(QUESTIONS))]

_stats = {"orders": 0, "payments": 0, "askdocs": 0, "errors": 0}


def _post(url: str, path: str, payload: dict | None = None) -> bool:
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url + path, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        _stats["errors"] += 1
        return False


def main() -> None:
    print(f"traffic → orders={ORDERS_URL} payments={PAYMENTS_URL} askdocs={ASKDOCS_URL} "
          f"(ask_every={ASK_EVERY}, askdocs_load={ASKDOCS_LOAD})")
    i = 0
    last_report = time.time()
    while True:
        i += 1
        if _post(ORDERS_URL, "/orders"):
            _stats["orders"] += 1
        if _post(PAYMENTS_URL, "/charge"):
            _stats["payments"] += 1
        if ASKDOCS_LOAD and i % ASK_EVERY == 0:
            question = random.choices(QUESTIONS, weights=_WEIGHTS, k=1)[0]
            if _post(ASKDOCS_URL, "/ask", {"question": question}):
                _stats["askdocs"] += 1

        if time.time() - last_report >= 10:
            print("sent:", _stats)
            last_report = time.time()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped:", _stats)
