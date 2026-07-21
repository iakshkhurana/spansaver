"""Central config for the auditor — every URL, key, price, and window comes from env.

Golden rule #5: no hardcoded URLs/keys/ports/prices anywhere in the codebase. This module is
the single place env is read; everything else imports `settings`. Values are loaded once at
import. When run outside docker (a bare CLI on the host), we also pull from a repo-root .env so
`python -m auditor.telemetry_auditor.introspect` works without exporting vars by hand.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

# Optional: load .env from the repo root for host-side CLI runs. Inside docker the values
# already come from env_file, so a missing python-dotenv is not fatal.
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except Exception:  # noqa: BLE001 - env may already be present; never block on this
    pass


@dataclass(frozen=True)
class ClickHouseDSN:
    """Parsed CLICKHOUSE_DSN, e.g. clickhouse://default:@clickhouse:9000/default.

    The native protocol (port 9000) is assumed — that's what the DSN in .env points at and
    what clickhouse-driver speaks. Host/port are overridable via CLICKHOUSE_HOST/PORT so the
    same code runs inside the SigNoz docker network (host `clickhouse`) or against a locally
    published port during dev.
    """

    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def parse(cls, dsn: str) -> "ClickHouseDSN":
        u = urlparse(dsn)
        host = os.getenv("CLICKHOUSE_HOST") or u.hostname or "localhost"
        port = int(os.getenv("CLICKHOUSE_PORT") or u.port or 9000)
        database = (u.path or "/default").lstrip("/") or "default"
        return cls(
            host=host,
            port=port,
            user=unquote(u.username or "default"),
            password=unquote(u.password or ""),
            database=database,
        )


def _f(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw not in (None, "") else default
    except ValueError:
        return default


def _i(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # SigNoz
    signoz_api_url: str = field(default_factory=lambda: os.getenv("SIGNOZ_API_URL", "http://localhost:8080"))
    signoz_ui_url: str = field(default_factory=lambda: os.getenv("SIGNOZ_UI_URL", "http://localhost:8080"))
    signoz_api_key: str = field(default_factory=lambda: os.getenv("SIGNOZ_API_KEY", ""))

    # ClickHouse
    clickhouse_dsn_raw: str = field(
        default_factory=lambda: os.getenv("CLICKHOUSE_DSN", "clickhouse://default:@clickhouse:9000/default")
    )

    # Pricing assumptions — always surfaced as "assumed rate" in the UI (golden rule #2).
    price_per_gb_ingest: float = field(default_factory=lambda: _f("PRICE_PER_GB_INGEST", 0.30))
    price_in_per_mtok: float = field(default_factory=lambda: _f("PRICE_IN_PER_MTOK", 3.00))
    price_out_per_mtok: float = field(default_factory=lambda: _f("PRICE_OUT_PER_MTOK", 15.00))
    # Metrics/traces have no clean per-GB proxy in ClickHouse, so their $ uses a per-million
    # rate. Datapoints/spans are MEASURED; only these rates are the assumption (golden rule #2).
    price_per_million_samples: float = field(default_factory=lambda: _f("PRICE_PER_MILLION_SAMPLES", 0.10))
    price_per_million_spans: float = field(default_factory=lambda: _f("PRICE_PER_MILLION_SPANS", 0.20))

    # Windows
    audit_window_hours: int = field(default_factory=lambda: _i("AUDIT_WINDOW_HOURS", 24))
    verify_window_minutes: int = field(default_factory=lambda: _i("VERIFY_WINDOW_MINUTES", 10))

    auditor_port: int = field(default_factory=lambda: _i("AUDITOR_PORT", 8100))

    # Where fixgen writes patches. Default = repo collector/; override COLLECTOR_DIR in the
    # auditor container (the compose mounts ./collector there).
    collector_dir: str = field(
        default_factory=lambda: os.getenv("COLLECTOR_DIR")
        or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "collector"))
    )

    @property
    def patches_dir(self) -> str:
        """ACTIVE patches: merge_config globs collector/patches/*.yaml on collector start, so a
        file here is live after the next collector restart. /apply copies here; /unapply removes."""
        return os.path.join(self.collector_dir, "patches")

    @property
    def generated_dir(self) -> str:
        """STAGED patches: fixgen writes here at /audit time. NOT globbed by merge_config, so a
        generated patch is inert until /apply promotes it into patches_dir. This keeps per-finding
        apply honest — a collector restart never activates a fix nobody applied."""
        return os.path.join(self.collector_dir, "generated")

    @property
    def clickhouse(self) -> ClickHouseDSN:
        return ClickHouseDSN.parse(self.clickhouse_dsn_raw)


settings = Settings()
