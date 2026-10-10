"""SQLite history of finished runs (small, local, no ORM)."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from .models import AnalysisResult, HistoryItem, JobInfo

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    created_at  REAL NOT NULL,
    finished_at REAL NOT NULL,
    verdict     TEXT NOT NULL,
    preset_id   TEXT,
    source      TEXT NOT NULL,
    stdin       TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_created ON runs(created_at DESC);
"""


class HistoryStore:
    def __init__(self, path: Path | str, keep: int = 200) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._keep = keep
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def save(self, job: JobInfo) -> None:
        if job.result is None:
            return
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.id, job.created_at, job.finished_at or time.time(),
                    job.result.verdict.verdict.value, job.preset_id,
                    job.source or "", job.stdin or "", job.result.model_dump_json(),
                ),
            )
            self._conn.execute(
                "DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY created_at DESC LIMIT ?)",
                (self._keep,),
            )
            self._conn.commit()

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, created_at, finished_at, preset_id, source, stdin, result_json"
                " FROM runs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return JobInfo(
            id=row[0], status="done", created_at=row[1], finished_at=row[2], preset_id=row[3],
            source=row[4], stdin=row[5], result=AnalysisResult.model_validate_json(row[6]),
        )

    def recent(self, limit: int = 20) -> list[HistoryItem]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, created_at, verdict, preset_id, source FROM runs"
                " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            HistoryItem(
                id=r[0], created_at=r[1], verdict=r[2], preset_id=r[3],
                source_preview=_preview(r[4]),
            )
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _preview(source: str) -> str:
    for line in source.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", "/*", "*", "//")):
            return s[:80]
    return source.strip()[:80]
