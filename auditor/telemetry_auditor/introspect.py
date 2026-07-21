"""Schema introspection CLI — run this FIRST, before writing any detector query.

Golden rule #1 (introspect, don't guess): SigNoz's ClickHouse table and column names drift
across versions. This tool discovers the live schema using ONLY ClickHouse's own stable
`system.*` tables (system.databases / system.tables / system.columns / system.parts), which
do not change between SigNoz versions. Nothing here hardcodes a signoz table name.

Usage (run inside the SigNoz docker network so `clickhouse` resolves):

    # Overview: signoz databases + their tables with row counts and on-disk size
    docker compose --profile full run --rm auditor python -m auditor.telemetry_auditor.introspect

    # Columns of a specific table (name comes from the overview above)
    ... introspect describe signoz_logs.logs

    # A few real rows, to pin attribute keys / severity values / metric names
    ... introspect sample signoz_logs.logs 3

Paste the overview + a describe/sample of the logs, traces, and metrics tables back into the
repo and we pin the confirmed names as constants next to each detector.
"""
from __future__ import annotations

import argparse
import sys

from auditor.telemetry_auditor.clickhouse import ClickHouse, ClickHouseUnavailable

SIGNOZ_DB_PREFIX = "signoz"


def _human_bytes(n: int | None) -> str:
    if not n:
        return "0 B"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def overview(ch: ClickHouse) -> None:
    """List signoz_* databases and every table in them with rows + on-disk bytes."""
    dbs = [r[0] for r in ch.query("SELECT name FROM system.databases ORDER BY name")]
    signoz_dbs = [d for d in dbs if d.startswith(SIGNOZ_DB_PREFIX)]
    print(f"databases (all): {dbs}")
    print(f"signoz databases: {signoz_dbs}\n")

    if not signoz_dbs:
        print("[!] no signoz_* databases found — is this the right ClickHouse instance?")
        return

    db_list = ", ".join(f"'{d}'" for d in signoz_dbs)
    # Size/rows from active parts (reliable for MergeTree); tables with no parts show 0.
    parts = ch.query(
        f"""
        SELECT database, table, sum(rows) AS rows, sum(bytes_on_disk) AS bytes
        FROM system.parts
        WHERE active AND database IN ({db_list})
        GROUP BY database, table
        """
    )
    size_by = {(d, t): (rows, byts) for d, t, rows, byts in parts}

    tables = ch.query(
        f"""
        SELECT database, name, engine
        FROM system.tables
        WHERE database IN ({db_list})
        ORDER BY database, name
        """
    )
    current_db = None
    for db, name, engine in tables:
        if db != current_db:
            print(f"\n== {db} ==")
            current_db = db
        rows, byts = size_by.get((db, name), (0, 0))
        print(f"  {name:<40} {_human_bytes(byts):>12}  {rows:>14,} rows  [{engine}]")


def describe(ch: ClickHouse, qualified: str) -> None:
    """Print columns (name + type) for db.table using system.columns."""
    if "." not in qualified:
        print("usage: introspect describe <database>.<table>", file=sys.stderr)
        sys.exit(2)
    db, table = qualified.split(".", 1)
    cols = ch.query(
        "SELECT name, type FROM system.columns WHERE database = %(db)s AND table = %(t)s ORDER BY position",
        {"db": db, "t": table},
    )
    if not cols:
        print(f"[!] no such table: {qualified}")
        return
    print(f"columns of {qualified}:")
    for name, ctype in cols:
        print(f"  {name:<32} {ctype}")


def sample(ch: ClickHouse, qualified: str, n: int) -> None:
    """Dump N real rows so we can pin attribute keys, severity values, metric names."""
    if "." not in qualified:
        print("usage: introspect sample <database>.<table> [N]", file=sys.stderr)
        sys.exit(2)
    rows, cols = ch.query(f"SELECT * FROM {qualified} LIMIT {int(n)}", with_columns=True)
    print(f"{qualified} — {len(rows)} row(s), columns: {cols}\n")
    for i, row in enumerate(rows):
        print(f"--- row {i} ---")
        for c, v in zip(cols, row):
            print(f"  {c:<28} = {v!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="introspect", description="Discover SigNoz ClickHouse schema")
    sub = parser.add_subparsers(dest="cmd")
    d = sub.add_parser("describe", help="columns of a db.table")
    d.add_argument("table")
    s = sub.add_parser("sample", help="N real rows of a db.table")
    s.add_argument("table")
    s.add_argument("n", nargs="?", type=int, default=3)
    args = parser.parse_args(argv)

    ch = ClickHouse()
    try:
        if not ch.ping():
            print("[!] ClickHouse ping returned unexpected result", file=sys.stderr)
            return 1
        if args.cmd == "describe":
            describe(ch, args.table)
        elif args.cmd == "sample":
            sample(ch, args.table, args.n)
        else:
            overview(ch)
    except ClickHouseUnavailable as e:
        print(f"\n[FAIL] {e}", file=sys.stderr)
        print(
            "\nHint: run this inside the SigNoz docker network so `clickhouse` resolves, e.g.\n"
            "  docker compose --profile full run --rm auditor python -m auditor.telemetry_auditor.introspect\n"
            "or set CLICKHOUSE_HOST/CLICKHOUSE_PORT to a locally published port.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
