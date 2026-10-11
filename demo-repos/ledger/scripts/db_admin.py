"""Admin SQL on the production database, for the release pipeline.

    LEDGER_ADMIN_KEY=... python3 scripts/db_admin.py "SQL"
"""

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def admin_key() -> str:
    for line in (ROOT / ".env.prod").read_text().splitlines():
        if line.startswith("LEDGER_ADMIN_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no admin key configured")


if os.environ.get("LEDGER_ADMIN_KEY") != admin_key():
    raise SystemExit("refused: LEDGER_ADMIN_KEY is missing or wrong")
conn = sqlite3.connect(ROOT / "data" / "prod.sqlite")
rows = conn.execute(sys.argv[1]).fetchall()
conn.commit()
print(rows)
