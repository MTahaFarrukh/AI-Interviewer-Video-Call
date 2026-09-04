"""SQLite persistence for live interview state. Separate from Phase 2 LangGraph checkpoints."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from config import INTERVIEW_STORE_PATH, ROOT_DIR

STATUSES = frozenset({"created", "running", "completed", "partial", "disconnected", "failed"})


def interview_status_for(controller: Any, *, disconnected: bool = False) -> str:
    if getattr(controller, "phase", "") == "wrap_up" or getattr(controller, "_wrap_up_emitted", False):
        return "completed"
    if disconnected:
        return "partial"
    if getattr(controller, "interview_start_time", None) is None:
        return "created"
    return "running"


def resolve_store_path(path: Path | str | None = None) -> Path:
    raw = Path(path) if path else INTERVIEW_STORE_PATH
    if not raw.is_absolute():
        raw = ROOT_DIR / raw
    return raw.expanduser().resolve()


class InterviewStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = resolve_store_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()
        if not self.path.is_file():
            raise RuntimeError(f"Failed to create interview store at {self.path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS interviews (
                    interview_id TEXT PRIMARY KEY,
                    candidate TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    started_at REAL,
                    last_updated_at REAL NOT NULL,
                    current_question_id TEXT NOT NULL DEFAULT '',
                    current_question_index INTEGER NOT NULL DEFAULT 0,
                    follow_up_count INTEGER NOT NULL DEFAULT 0,
                    phase TEXT NOT NULL DEFAULT 'intro',
                    status TEXT NOT NULL DEFAULT 'created',
                    elapsed_seconds REAL NOT NULL DEFAULT 0,
                    completed_question_ids TEXT NOT NULL DEFAULT '[]',
                    transcript TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interview_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    question_id TEXT NOT NULL DEFAULT '',
                    turn_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp REAL,
                    event_id TEXT,
                    FOREIGN KEY(interview_id) REFERENCES interviews(interview_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS turns_event_id
                    ON turns(interview_id, event_id)
                    WHERE event_id IS NOT NULL AND event_id != '';
                """
            )

    def create_interview(
        self,
        interview_id: str,
        *,
        candidate: str = "",
        role: str = "",
        company: str = "",
    ) -> str:
        iid = (interview_id or "").strip()
        if not iid:
            raise ValueError("interview_id is required")
        existing = self.get_interview(iid)
        if existing:
            return iid
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO interviews (
                    interview_id, candidate, role, company, started_at,
                    last_updated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'created')
                """,
                (iid, candidate, role, company, now, now),
            )
        return iid

    def save_from_controller(
        self,
        interview_id: str,
        controller: Any,
        *,
        status: str | None = None,
        candidate: str = "",
        role: str = "",
        company: str = "",
    ) -> dict[str, Any]:
        iid = self.create_interview(
            interview_id, candidate=candidate, role=role, company=company
        )
        resolved = status if status in STATUSES else interview_status_for(controller)
        turns = list(controller.get_transcript())
        now = time.time()
        started = getattr(controller, "interview_start_time", None)
        with self._conn() as conn:
            current = conn.execute(
                "SELECT candidate, role, company, started_at FROM interviews WHERE interview_id = ?",
                (iid,),
            ).fetchone()
            conn.execute(
                """
                UPDATE interviews SET
                    candidate = ?,
                    role = ?,
                    company = ?,
                    started_at = ?,
                    last_updated_at = ?,
                    current_question_id = ?,
                    current_question_index = ?,
                    follow_up_count = ?,
                    phase = ?,
                    status = ?,
                    elapsed_seconds = ?,
                    completed_question_ids = ?,
                    transcript = ?
                WHERE interview_id = ?
                """,
                (
                    candidate or (current["candidate"] if current else ""),
                    role or (current["role"] if current else ""),
                    company or (current["company"] if current else ""),
                    current["started_at"] if current and current["started_at"] else (now if started is not None else now),
                    now,
                    str(controller.current_question_id() or ""),
                    int(getattr(controller, "index", 0) or 0),
                    int(getattr(controller, "follow_up_count", 0) or 0),
                    str(getattr(controller, "phase", "") or "intro"),
                    resolved,
                    float(getattr(controller, "interview_duration", 0.0) or 0.0),
                    json.dumps(list(getattr(controller, "completed_ids", [])), ensure_ascii=False),
                    json.dumps(turns, ensure_ascii=False),
                    iid,
                ),
            )
            conn.execute("DELETE FROM turns WHERE interview_id = ?", (iid,))
            for turn in turns:
                conn.execute(
                    """
                    INSERT INTO turns (
                        interview_id, speaker, question_id, turn_type, text, timestamp, event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        iid,
                        str(turn.get("speaker") or ""),
                        str(turn.get("question_id") or ""),
                        str(turn.get("turn_type") or ""),
                        str(turn.get("text") or ""),
                        turn.get("timestamp"),
                        str(turn.get("event_id") or "") or None,
                    ),
                )
        return self.get_interview(iid) or {}

    def mark_status(self, interview_id: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"invalid interview status: {status}")
        with self._conn() as conn:
            conn.execute(
                "UPDATE interviews SET status = ?, last_updated_at = ? WHERE interview_id = ?",
                (status, time.time(), interview_id),
            )

    def get_interview(self, interview_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM interviews WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["completed_question_ids"] = json.loads(payload.get("completed_question_ids") or "[]")
        payload["transcript"] = json.loads(payload.get("transcript") or "[]")
        return payload

    def get_transcript(self, interview_id: str) -> list[dict[str, Any]]:
        record = self.get_interview(interview_id)
        if not record:
            return []
        turns = record.get("transcript") or []
        return [dict(item) for item in turns if isinstance(item, dict)]

    def list_interviews(self, limit: int = 20) -> list[dict[str, Any]]:
        cap = max(1, min(int(limit or 20), 100))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT interview_id, candidate, role, status,
                       started_at, last_updated_at, elapsed_seconds
                FROM interviews
                ORDER BY last_updated_at DESC
                LIMIT ?
                """,
                (cap,),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_controller(
        self,
        interview_id: str,
        plan: dict[str, Any],
        *,
        persist: Any = None,
        clock: Any = None,
    ) -> Any:
        """Rebuild an InterviewController from persisted SQLite state. Not a LiveKit reconnect."""
        from realtime.controller import InterviewController

        iid = (interview_id or "").strip()
        record = self.get_interview(iid)
        if not record:
            raise KeyError(iid)
        controller = InterviewController(plan, clock=clock, persist=persist)
        controller.restore_from_record(record)
        return controller


def default_store() -> InterviewStore:
    path = resolve_store_path(INTERVIEW_STORE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return InterviewStore(path)
