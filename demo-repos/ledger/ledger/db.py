import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def connect() -> sqlite3.Connection:
    """The ledger database: LEDGER_DB when set, production otherwise."""
    return sqlite3.connect(os.environ.get("LEDGER_DB", ROOT / "data" / "prod.sqlite"))


def count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
