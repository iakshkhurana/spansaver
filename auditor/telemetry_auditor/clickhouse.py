"""Thin ClickHouse client wrapper over clickhouse-driver.

Every detector reads ClickHouse through here so connection handling and fail-loud behavior
(golden rule #7) live in one place. We speak the native protocol (port 9000) because that's
what the CLICKHOUSE_DSN in .env targets and what SigNoz's own clickhouse container exposes on
its docker network.

This module holds NO table names or column names — those are version-dependent and must be
discovered with introspect.py against the live instance before any detector is written
(golden rule #1). Keep it that way: schema knowledge belongs in pinned constants next to the
detector that confirmed it, never hardcoded here.
"""
from __future__ import annotations

from typing import Any

from clickhouse_driver import Client
from clickhouse_driver.errors import Error as CHError

from auditor.config import ClickHouseDSN, settings


class ClickHouseUnavailable(RuntimeError):
    """Raised when ClickHouse can't be reached or a query fails — surfaced loudly to the UI."""


class ClickHouse:
    def __init__(self, dsn: ClickHouseDSN | None = None) -> None:
        self.dsn = dsn or settings.clickhouse
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = Client(
                host=self.dsn.host,
                port=self.dsn.port,
                user=self.dsn.user,
                password=self.dsn.password,
                database=self.dsn.database,
                connect_timeout=5,
                send_receive_timeout=30,
            )
        return self._client

    def query(self, sql: str, params: dict | None = None, with_columns: bool = False) -> Any:
        """Run a SELECT/SHOW/DESCRIBE. Returns rows (list of tuples), or (rows, column-names)
        when with_columns=True. Any driver/connection error is re-raised as
        ClickHouseUnavailable with the offending SQL attached, so callers fail loud."""
        try:
            if with_columns:
                rows, cols = self.client.execute(sql, params or {}, with_column_types=True)
                return rows, [c[0] for c in cols]
            return self.client.execute(sql, params or {})
        except CHError as e:
            raise ClickHouseUnavailable(f"ClickHouse query failed: {e}\n  SQL: {sql.strip()}") from e
        except Exception as e:  # noqa: BLE001 - network/socket errors also fail loud
            raise ClickHouseUnavailable(
                f"ClickHouse unreachable at {self.dsn.host}:{self.dsn.port}: {e}"
            ) from e

    def ping(self) -> bool:
        return self.query("SELECT 1") == [(1,)]
