"""InterviewSessionStore boundary.

Phase 1 keeps the existing SQLite `InterviewStore` as the live transcript/session
implementation. This module documents and wraps that store for future SaaS binding.

Mapping (legacy → product):
- InterviewStore.interviews.interview_id  → product Interview.id (string id today)
- livekit room / identity                 → Interview.livekit_room_name (SaaS)
- turns + transcript JSON                 → future InterviewTurn / TranscriptSegment
- status/phase/elapsed                    → Interview status + timestamps

Do not dual-write yet. Agent continues to use realtime.store.InterviewStore directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from realtime.store import InterviewStore, resolve_store_path


class InterviewSessionStore(ABC):
    @abstractmethod
    def create_session(
        self,
        interview_id: str,
        *,
        candidate: str = "",
        role: str = "",
        company: str = "",
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, interview_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def path(self) -> Path:
        raise NotImplementedError


class SqliteInterviewSessionStore(InterviewSessionStore):
    """Thin adapter around the existing live SQLite InterviewStore."""

    def __init__(self, store: InterviewStore | None = None, path: Path | None = None) -> None:
        self._store = store or InterviewStore(path=path)

    def create_session(
        self,
        interview_id: str,
        *,
        candidate: str = "",
        role: str = "",
        company: str = "",
    ) -> str:
        return self._store.create_interview(
            interview_id, candidate=candidate, role=role, company=company
        )

    def get_session(self, interview_id: str) -> dict[str, Any] | None:
        return self._store.get_interview(interview_id)

    def path(self) -> Path:
        return resolve_store_path(self._store.path)

    @property
    def legacy_store(self) -> InterviewStore:
        return self._store
