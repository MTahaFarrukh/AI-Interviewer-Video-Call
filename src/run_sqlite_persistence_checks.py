"""Offline checks that the live interview SQLite file is actually created on disk."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import CHECKPOINT_PATH, INTERVIEW_STORE_PATH, ROOT_DIR
from realtime.controller import InterviewController
from realtime.store import InterviewStore, interview_status_for, resolve_store_path
from run_phase3_slice1_checks import record
from run_phase3_slice2_checks import _twelve_question_plan
from run_phase3_slice3_checks import _adequate_for, _shallow
from run_phase6_checks import _speak
from run_phase8_checks import main as phase8_main


def test_sqlite_file_persistence() -> None:
    plan = _twelve_question_plan()
    plan["candidate"] = {"name": "Muhammad Taha Farrukh"}
    plan["job"] = {"role": "Junior AI Engineer", "company": "Northwind Labs"}

    record(
        "configured live store is absolute under project output/live",
        INTERVIEW_STORE_PATH.is_absolute()
        and INTERVIEW_STORE_PATH.parent == ROOT_DIR / "output" / "live"
        and INTERVIEW_STORE_PATH.name == "interview.sqlite"
        and INTERVIEW_STORE_PATH != CHECKPOINT_PATH,
    )
    record(
        "live store path is not the Phase 2 LangGraph checkpoint",
        resolve_store_path().resolve() != Path(CHECKPOINT_PATH).resolve(),
    )

    with tempfile.TemporaryDirectory() as tmp:
        parent = Path(tmp) / "live"
        db_path = parent / "interview.sqlite"
        record("database directory is automatically created", not parent.exists())
        store = InterviewStore(db_path)
        record(
            "database file is actually created",
            parent.is_dir() and store.path.is_file() and store.path.resolve() == db_path.resolve(),
        )
        iid = store.create_interview(
            "int-persist",
            candidate="Muhammad Taha Farrukh",
            role="Junior AI Engineer",
            company="Northwind Labs",
        )

        def persist(controller: InterviewController) -> None:
            store.save_from_controller(
                iid,
                controller,
                candidate="Muhammad Taha Farrukh",
                role="Junior AI Engineer",
                company="Northwind Labs",
            )

        controller = InterviewController(plan, persist=persist)
        controller.start_interview()
        q1 = str((controller.current_question() or {}).get("question") or "Q1")
        controller.record_interviewer_turn(q1, "question")
        _speak(controller, _shallow(), event_id="a1")
        row = store.get_interview(iid)
        record(
            "interview row persists",
            row is not None
            and row["interview_id"] == iid
            and row["candidate"] == "Muhammad Taha Farrukh"
            and store.path.is_file(),
        )
        record(
            "completed turns persist",
            len(store.get_transcript(iid)) >= 2
            and store.get_transcript(iid)[0]["text"] == q1,
        )

        status = interview_status_for(controller, disconnected=True)
        store.save_from_controller(iid, controller, status=status)
        record(
            "disconnect/partial state persists",
            store.get_interview(iid)["status"] == "partial",
        )
        expected_turns = controller.get_transcript()
        reopened = InterviewStore(db_path)
        loaded = reopened.get_interview(iid)
        record(
            "reopening the database from a fresh connection can read the interview",
            loaded is not None and loaded["interview_id"] == iid and reopened.path.is_file(),
        )
        record(
            "the persisted transcript matches the controller transcript",
            loaded is not None and loaded["transcript"] == expected_turns,
        )

        import mcp_server

        mcp_server.configure(store_path=db_path)
        mcp_status = mcp_server.get_interview_status(iid)
        mcp_turns = mcp_server.get_interview_transcript(iid)
        mcp_report = mcp_server.get_interview_report(iid)
        record(
            "Phase 7 MCP can read the persisted interview",
            mcp_status.get("ok") is True
            and mcp_status.get("candidate") == "Muhammad Taha Farrukh"
            and mcp_turns.get("ok") is True
            and len(mcp_turns.get("turns") or []) == len(expected_turns)
            and mcp_report.get("ok") is True,
        )
        mcp_server.configure()

        done = InterviewController(plan)
        for i in range(12):
            q = done.current_question() or {}
            done.record_interviewer_turn(str(q.get("question") or f"q{i+1}"), "question")
            _speak(done, _adequate_for(q), event_id=f"done-{i+1}")
        store.save_from_controller("int-done", done, status="completed")
        record(
            "wrap-up/completed state persists",
            store.get_interview("int-done")["status"] == "completed"
            and done.phase == "wrap_up",
        )

        sqlite_files = sorted(p.resolve() for p in parent.glob("*.sqlite"))
        record(
            "no second SQLite database is created",
            sqlite_files == [store.path.resolve()]
            and store.path.resolve() != Path(CHECKPOINT_PATH).resolve(),
        )


def main() -> int:
    print("=== SQLite persistence checks ===")
    test_sqlite_file_persistence()
    return phase8_main()


if __name__ == "__main__":
    raise SystemExit(main())
