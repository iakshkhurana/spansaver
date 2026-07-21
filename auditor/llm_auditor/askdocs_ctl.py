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


def _post(path: str, payload: dict) -> dict:
    url = f"{ASKDOCS_URL.rstrip('/')}{path}"
    try:
        resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001 - surface any HTTP/connection error loudly
        raise AskdocsControlError(
            f"could not reach askdocs at {url}: {e}. Is askdocs up, and is ASKDOCS_URL set to "
            "the service reachable from the auditor (default http://askdocs:8000)?"
        ) from e


# Each LLM fix maps to one askdocs admin flip. apply = the fixed (non-wasteful) state; unapply =
# back to the wasteful "before". L1 = exact-match cache on; L2 = full-docs preamble off.
_APPLY = {
    "L1": lambda: _post("/admin/cache", {"enabled": True}),
    "L2": lambda: _post("/admin/bloat", {"enabled": False}),
}
_UNAPPLY = {
    "L1": lambda: _post("/admin/cache", {"enabled": False, "clear": True}),
    "L2": lambda: _post("/admin/bloat", {"enabled": True}),
}


def apply(finding_id: str = "L1") -> dict:
    """Apply an LLM fix by flipping the matching askdocs runtime toggle."""
    fn = _APPLY.get(finding_id.upper())
    if fn is None:
        raise AskdocsControlError(f"no askdocs apply action for finding {finding_id}")
    return {"applied": finding_id.upper(), "target": "askdocs", **fn()}


def unapply(finding_id: str = "L1") -> dict:
    """Reverse an LLM fix, restoring the wasteful 'before' state on the live service."""
    fn = _UNAPPLY.get(finding_id.upper())
    if fn is None:
        raise AskdocsControlError(f"no askdocs unapply action for finding {finding_id}")
    return {"unapplied": finding_id.upper(), "target": "askdocs", **fn()}
