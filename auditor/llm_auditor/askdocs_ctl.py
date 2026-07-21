"""Apply / unapply the L1 fix by flipping askdocs' cache at runtime.

L1's fix is a config change, not a collector patch (LEAK-CATALOG L1), so its apply path does not
touch the collector. Instead we POST to askdocs' /admin/cache endpoint, which flips the exact-
match, TTL-bounded response cache on the running service — instant and reversible. This is the
LLM-domain analogue of collector_ctl: same fail-loud contract (golden rule #7), same
apply/unapply shape so main.py can dispatch by finding domain.
"""
from __future__ import annotations

import os

import httpx

# askdocs is reachable by service name on the compose network; overridable for host-side runs.
ASKDOCS_URL = os.getenv("ASKDOCS_URL", "http://askdocs:8000")
_TIMEOUT = float(os.getenv("ASKDOCS_CTL_TIMEOUT", "10"))


class AskdocsControlError(RuntimeError):
    pass


def _post_cache(enabled: bool, clear: bool = False) -> dict:
    url = f"{ASKDOCS_URL.rstrip('/')}/admin/cache"
    try:
        resp = httpx.post(url, json={"enabled": enabled, "clear": clear}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001 - surface any HTTP/connection error loudly
        raise AskdocsControlError(
            f"could not reach askdocs at {url}: {e}. Is askdocs up, and is ASKDOCS_URL set to "
            "the service reachable from the auditor (default http://askdocs:8000)?"
        ) from e


def apply(finding_id: str = "L1") -> dict:
    """Turn the cache on — this is applying the L1 fix on the live service."""
    state = _post_cache(enabled=True)
    return {"applied": finding_id, "target": "askdocs", **state}


def unapply(finding_id: str = "L1") -> dict:
    """Turn the cache off and clear it, restoring the genuinely-uncached 'before' state."""
    state = _post_cache(enabled=False, clear=True)
    return {"unapplied": finding_id, "target": "askdocs", **state}
