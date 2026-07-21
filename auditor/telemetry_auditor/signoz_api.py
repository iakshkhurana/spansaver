"""SigNoz REST API client — routes CONFIRMED against the live instance, auth pending key.

VERIFIED 2026-07-21 against SigNoz v0.133.0 (EE) at SIGNOZ_API_URL:
    GET /api/v1/version   -> 200 {"version":"v0.133.0","ee":"Y","setupCompleted":true}  (no auth)
    GET /api/v1/health    -> 200 {"status":"ok"}                                          (no auth)
    GET /api/v1/dashboards-> 401 {"error":{"type":"unauthenticated"}}   (route exists; needs key)
    GET /api/v1/rules     -> 401 {"error":{"type":"unauthenticated"}}   (route exists; needs key)

Golden rule #1: the routes above are pinned from real responses, not docs. What is NOT yet
confirmed on THIS instance is the auth header name and the dashboard/alert JSON shape — both
need a real API key (SigNoz → Settings → API Keys, admin) in .env as SIGNOZ_API_KEY. SigNoz
authenticates API keys via the `SIGNOZ-API-KEY` header; `ping_auth()` below proves it (200 vs
401) the moment a key is set, and `dashboards()`/`alert_rules()` dump raw JSON so we can pin
the metric-reference extraction shape from a real payload before wiring it into the T2 detector.
"""
from __future__ import annotations

import argparse
import json
import sys

import httpx

from auditor.config import settings

# ─── Confirmed routes (see module docstring for the live responses) ───────────
ROUTE_VERSION = "/api/v1/version"      # 200, no auth
ROUTE_HEALTH = "/api/v1/health"        # 200, no auth
ROUTE_DASHBOARDS = "/api/v1/dashboards"  # 401 without key — route confirmed
ROUTE_RULES = "/api/v1/rules"          # 401 without key — alert rules; route confirmed

AUTH_HEADER = "SIGNOZ-API-KEY"         # confirmed by ping_auth() once a key exists


class SigNozAPIError(RuntimeError):
    """Fail loud (golden rule #7): unreachable API, auth failure, or non-2xx surfaced here."""


class SigNozAPI:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or settings.signoz_api_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.signoz_api_key
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict:
        return {AUTH_HEADER: self.api_key} if self.api_key else {}

    def _get(self, route: str, auth: bool = True) -> dict | list:
        url = self.base_url + route
        try:
            resp = self._client.get(url, headers=self._headers() if auth else {})
        except httpx.HTTPError as e:
            raise SigNozAPIError(f"SigNoz API unreachable at {url}: {e}") from e
        if resp.status_code == 401:
            raise SigNozAPIError(
                f"401 unauthenticated on {route} — set SIGNOZ_API_KEY in .env "
                "(SigNoz → Settings → API Keys, admin)."
            )
        if resp.status_code >= 400:
            raise SigNozAPIError(f"{resp.status_code} on {route}: {resp.text[:300]}")
        return resp.json()

    # ── Unauthenticated ──
    def version(self) -> dict:
        return self._get(ROUTE_VERSION, auth=False)  # type: ignore[return-value]

    def health(self) -> dict:
        return self._get(ROUTE_HEALTH, auth=False)  # type: ignore[return-value]

    def ping_auth(self) -> bool:
        """True if the API key authenticates (dashboards route returns 2xx)."""
        try:
            self._get(ROUTE_DASHBOARDS)
            return True
        except SigNozAPIError:
            return False

    # ── Authenticated (need SIGNOZ_API_KEY) ──
    def dashboards(self) -> dict | list:
        return self._get(ROUTE_DASHBOARDS)

    def alert_rules(self) -> dict | list:
        return self._get(ROUTE_RULES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signoz_api", description="Probe/pin the SigNoz REST API")
    parser.add_argument(
        "cmd",
        nargs="?",
        default="ping",
        choices=["ping", "dashboards", "rules"],
        help="ping = version+health+auth check; dashboards/rules = dump raw JSON",
    )
    args = parser.parse_args(argv)
    api = SigNozAPI()
    try:
        if args.cmd == "ping":
            print("version:", json.dumps(api.version()))
            print("health :", json.dumps(api.health()))
            authed = api.ping_auth()
            print(f"auth   : {'OK (key accepted)' if authed else 'NO KEY / rejected — set SIGNOZ_API_KEY'}")
            return 0 if authed else 1
        payload = api.dashboards() if args.cmd == "dashboards" else api.alert_rules()
        print(json.dumps(payload, indent=2)[:8000])
    except SigNozAPIError as e:
        print(f"\n[FAIL] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
