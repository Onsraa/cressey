import sqlite3
from pathlib import Path

from cressey.domain.guides import Guide


class GuideStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS guides (id TEXT PRIMARY KEY, incident_id TEXT, json TEXT)"
            )

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def put(self, guide: Guide) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO guides VALUES (?, ?, ?)",
                (guide.id, guide.incident_id, guide.model_dump_json()),
            )

    def get(self, gid: str) -> Guide | None:
        with self._db() as db:
            row = db.execute("SELECT json FROM guides WHERE id = ?", (gid,)).fetchone()
        return Guide.model_validate_json(row[0]) if row else None
