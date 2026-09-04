"""Offline checks for Phase 3 Slice 1: approved-plan gate + Q1 briefing."""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import AGENT_NAME, GEMINI_LIVE_MODEL, QUESTION_PLAN_PATH
from plan_loader import (
    compact_briefing,
    is_ready_for_live_interview,
    load_approved_plan,
    opening_instructions,
)
from realtime.controller import InterviewController

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{': ' + detail if detail else ''}")


def _sample_plan(*, status: str = "approved", questions: list | None = None) -> dict:
    return {
        "candidate": {"name": "Test Candidate"},
        "job": {"role": "Junior AI Engineer", "company": "Northwind Labs"},
        "approval_status": status,
        "approved_by_human": status in {"approved", "edited"},
        "questions": questions
        if questions is not None
        else [
            {
                "id": "q1",
                "category": "Technical",
                "question": "Walk me through your experience building REST APIs.",
                "competency": "Technical depth",
                "rationale": "Need a shipped API story.",
                "expected_evidence": "Mentions routes, validation, errors.",
                "source": "resume",
                "source_reference": "Voice Notes API",
            }
        ],
    }


def test_plan_gate() -> None:
    missing = Path(tempfile.gettempdir()) / "firstround-missing-question-plan.json"
    if missing.exists():
        missing.unlink()
    record(
        "missing question_plan.json -> interview refuses to start",
        load_approved_plan(missing) is None
        and not is_ready_for_live_interview(load_approved_plan(missing)),
    )

    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "question_plan.json"
        bad.write_text("{not-json", encoding="utf-8")
        record(
            "invalid JSON -> refuses to start",
            load_approved_plan(bad) is None
            and not is_ready_for_live_interview(load_approved_plan(bad)),
        )

        unapproved = Path(tmp) / "unapproved.json"
        unapproved.write_text(
            json.dumps(_sample_plan(status="draft")),
            encoding="utf-8",
        )
        loaded = load_approved_plan(unapproved)
        record(
            "unapproved plan -> refuses to start",
            loaded is None or not is_ready_for_live_interview(loaded),
        )

        edited = Path(tmp) / "edited.json"
        edited.write_text(json.dumps(_sample_plan(status="edited")), encoding="utf-8")
        edited_plan = load_approved_plan(edited)
        record(
            "edited-but-not-approved plan -> live gate refuses",
            edited_plan is not None and not is_ready_for_live_interview(edited_plan),
        )

        approved = Path(tmp) / "approved.json"
        approved.write_text(json.dumps(_sample_plan(status="approved")), encoding="utf-8")
        approved_plan = load_approved_plan(approved)
        record(
            "approved plan -> controller loads",
            is_ready_for_live_interview(approved_plan)
            and InterviewController(approved_plan).current_question_id() == "q1",
        )


def test_disk_plan_and_briefing() -> None:
    plan = load_approved_plan(QUESTION_PLAN_PATH)
    ready = is_ready_for_live_interview(plan)
    record("disk plan is approved and ready", ready, QUESTION_PLAN_PATH.name)
    if not plan:
        record("exactly 12 questions detected", False, "no plan")
        record("Q1 is loaded from the plan", False, "no plan")
        record("compact briefing contains Q1", False, "no plan")
        record("compact briefing does NOT contain all 12 questions", False, "no plan")
        return

    questions = [q for q in (plan.get("questions") or []) if isinstance(q, dict)]
    record("exactly 12 questions detected", len(questions) == 12, str(len(questions)))

    controller = InterviewController(plan)
    q1 = controller.current_question() or {}
    disk_q1 = questions[0] if questions else {}
    record(
        "Q1 is loaded from the plan",
        controller.phase == "intro"
        and controller.current_question_id() == str(disk_q1.get("id") or "")
        and str(q1.get("question") or "") == str(disk_q1.get("question") or "")
        and bool(q1.get("question")),
        str(controller.current_question_id()),
    )

    briefing = compact_briefing(plan, controller.current_question_id())
    blob = json.dumps(briefing, ensure_ascii=False)
    q1_text = str(disk_q1.get("question") or "")
    other_texts = [str(q.get("question") or "") for q in questions[1:] if q.get("question")]
    leaked = [text for text in other_texts if text and text in blob]
    record(
        "compact briefing contains Q1",
        briefing.get("question") == q1_text and q1_text in blob,
        briefing.get("question_id", ""),
    )
    record(
        "compact briefing does NOT contain all 12 questions",
        not leaked and "questions" not in briefing,
        f"leaked={len(leaked)}",
    )
    record(
        "compact briefing stays current-turn only",
        briefing.get("candidate_name") == (plan.get("candidate") or {}).get("name")
        and "raw_resume" not in briefing
        and "jd_text" not in briefing
        and "readme" not in blob.lower()
        and "education" not in briefing
        and "experience" not in briefing,
    )
    opening = opening_instructions(briefing, str(briefing.get("candidate_name") or ""))
    record(
        "opening instructions use approved Q1 text",
        q1_text in opening and "introduce themselves" not in opening.lower(),
    )


def test_phase1_realtime_unchanged() -> None:
    import agent

    source = Path(inspect.getsourcefile(agent)).read_text(encoding="utf-8")
    model_src = inspect.getsource(agent._realtime_model)
    logging_src = inspect.getsource(agent._attach_turn_logging)
    session_src = inspect.getsource(agent.interview_session)

    record("existing Phase 1 RealtimeModel still constructs", agent._realtime_model() is not None)
    record(
        "Gemini Live model id unchanged",
        GEMINI_LIVE_MODEL == "gemini-2.5-flash-native-audio-preview-12-2025"
        and "model=GEMINI_LIVE_MODEL" in model_src,
    )
    record(
        "RealtimeModel voice/compression/resumption unchanged",
        'voice="Puck"' in model_src
        and "temperature=0.7" in model_src
        and "trigger_tokens=25600" in model_src
        and "target_tokens=12000" in model_src
        and "SessionResumptionConfig" in model_src,
    )
    record(
        "latency logging unchanged",
        "[LATENCY] candidate_stop_to_agent_audio_ms=" in logging_src
        and "[INTERRUPT] Agent interrupted" in logging_src,
    )
    record(
        "LiveKit room/session options unchanged",
        "room_io.AudioInputOptions()" in session_src
        and "text_output=False" in session_src
        and AGENT_NAME == "firstround-interviewer",
    )
    record(
        "plan gate fails closed before session start",
        "No approved interview plan — refusing interview" in session_src
        and session_src.find("is_ready_for_live_interview") < session_src.find("session.start"),
    )
    record(
        "generate_reply uses compact Q1 briefing, not demo intro",
        "opening_instructions" in session_src
        and "introduce themselves" not in session_src
        and "compact_briefing" in session_src,
    )
    record(
        "RealtimeModel constructor body not rewritten",
        "instructions=INTERVIEWER_INSTRUCTIONS" in model_src
        and "input_audio_transcription" in model_src,
    )
    record(
        "2D face / vendor-avatar stance unchanged",
        "Vendor avatar disabled (local 2D face only)" in source,
    )


def main() -> int:
    print("=== Phase 3 Slice 1 checks ===")
    test_plan_gate()
    test_disk_plan_and_briefing()
    test_phase1_realtime_unchanged()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
