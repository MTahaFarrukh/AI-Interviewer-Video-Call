from __future__ import annotations

from services.interview_session_store import SqliteInterviewSessionStore
from realtime.store import InterviewStore


def test_sqlite_session_store_wraps_legacy_store(tmp_path) -> None:
    db_path = tmp_path / "interview.sqlite"
    legacy = InterviewStore(path=db_path)
    store = SqliteInterviewSessionStore(store=legacy)
    iid = store.create_session("sess-1", candidate="Alex", role="Engineer", company="Acme")
    assert iid == "sess-1"
    row = store.get_session("sess-1")
    assert row is not None
    assert row["candidate"] == "Alex"
    assert store.path() == db_path.resolve()
    assert store.legacy_store is legacy
