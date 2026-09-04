"""Offline checks for Phase 3 Slice 3: follow-ups + 8-minute timer."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from plan_loader import compact_briefing, follow_up_instructions
from realtime.controller import INTERVIEW_LIMIT_SECONDS, MAX_FOLLOW_UPS, InterviewController
from realtime.evaluate import classify_answer
from run_phase3_slice1_checks import RESULTS, record, test_phase1_realtime_unchanged
from run_phase3_slice2_checks import (
    _twelve_question_plan,
    test_agent_hooks_unchanged,
    test_disk_plan_and_briefing,
    test_duplicate_and_wrap_guard,
    test_linear_controller,
    test_plan_gate,
    test_q2_briefing_isolation,
)


def _clock(box: dict) -> float:
    return float(box["now"])


def _speak(controller: InterviewController, text: str) -> str:
    controller.note_question_asked()
    controller.mark_candidate_speaking()
    return controller.try_complete_answer(text)


def _shallow() -> str:
    return "Yeah I did that."


def _strong_for(question: dict) -> str:
    q = str(question.get("question") or "the project")
    return (
        f"For {q} I parsed documents, used chunk size 500 with overlap 50, "
        f"generated embeddings, stored vectors in Chroma, and retrieved top-k "
        f"passages because that improved faithfulness on 40 gold questions. "
        f"I also logged retrieval misses so I could debug empty context windows."
    )


def _adequate_for(question: dict) -> str:
    q = str(question.get("question") or "the topic")
    return (
        f"I can answer {q} I used a concrete example with validation, tests, "
        f"and a clear trade-off because that made the design easier to debug."
    )


def _github_question() -> dict:
    return {
        "id": "q4",
        "category": "Technical",
        "question": (
            "In the langchain repository, the file libs/core/langchain_core/_api/internal.py "
            "uses inspect in is_caller_internal. What are the trade-offs?"
        ),
        "expected_evidence": "Discuss inspect stack frames and runtime cost.",
        "file": "libs/core/langchain_core/_api/internal.py",
        "repository": "langchain",
        "commit": "a92c032ff69ca6ec84451f8e13af1109d1a4f9ca",
        "follow_up_triggers": ["cannot explain inspect usage"],
    }


def test_follow_up_controller() -> None:
    plan = _twelve_question_plan()
    controller = InterviewController(plan)
    record(
        "Q1 starts with follow_up_count=0",
        controller.current_question_id() == "q1"
        and controller.follow_up_count == 0
        and MAX_FOLLOW_UPS == 2,
    )

    first = _speak(controller, _shallow())
    record(
        "shallow answer -> follow-up #1",
        first == "follow_up"
        and controller.current_question_id() == "q1"
        and controller.follow_up_count == 1
        and controller.last_eval == "shallow"
        and controller.completed_ids == [],
    )

    second = _speak(controller, _shallow())
    record(
        "shallow second answer -> follow-up #2",
        second == "follow_up"
        and controller.current_question_id() == "q1"
        and controller.follow_up_count == 2,
    )

    third = _speak(controller, _shallow())
    record(
        "third attempt -> forced Q2",
        third == "next"
        and controller.current_question_id() == "q2"
        and controller.follow_up_count == 0
        and controller.completed_ids == ["q1"],
    )
    record(
        "follow-up never becomes #3",
        controller.follow_up_count == 0 and MAX_FOLLOW_UPS == 2,
    )

    adequate = InterviewController(plan)
    action = _speak(adequate, _adequate_for(adequate.current_question() or {}))
    record(
        "adequate answer -> Q2",
        action == "next"
        and adequate.current_question_id() == "q2"
        and adequate.follow_up_count == 0,
    )

    strong = InterviewController(plan)
    action = _speak(strong, _strong_for(strong.current_question() or {}))
    record(
        "strong answer -> Q2",
        action == "next"
        and strong.current_question_id() == "q2"
        and strong.last_eval == "strong",
        str(strong.last_eval),
    )

    off = InterviewController(plan)
    action = _speak(
        off,
        "I spent the weekend baking sourdough and organizing my spice rack in great detail.",
    )
    record(
        "off-topic -> follow-up",
        action == "follow_up"
        and off.last_eval == "off_topic"
        and off.current_question_id() == "q1"
        and off.follow_up_count == 1,
    )

    bluff_plan = {
        "candidate": {"name": "Test"},
        "questions": [_github_question()]
        + _twelve_question_plan()["questions"][1:],
    }
    bluff = InterviewController(bluff_plan)
    action = _speak(
        bluff,
        "I implemented the whole pipeline in totally_secret_kernel.py "
        "and shipped commit deadbeef1234567 myself last week.",
    )
    briefing = compact_briefing(bluff_plan, "q4")
    probe = follow_up_instructions(briefing, "bluff", 1)
    record(
        "bluff -> evidence follow-up",
        action == "follow_up"
        and bluff.last_eval == "bluff"
        and bluff.current_question_id() == "q4"
        and "file or implementation" in probe.lower()
        and "deadbeef" not in probe
        and "totally_secret_kernel.py" not in probe,
        str(bluff.last_eval),
    )

    reset = InterviewController(plan)
    _speak(reset, _shallow())
    _speak(reset, _adequate_for(reset.current_question() or {}))
    record(
        "follow_up_count resets when moving Q1 -> Q2",
        reset.current_question_id() == "q2" and reset.follow_up_count == 0,
    )


def test_classifier() -> None:
    q1 = _twelve_question_plan()["questions"][0]
    record(
        "clear strong answer",
        classify_answer(_strong_for(q1), q1) == "strong",
    )
    record(
        "clear adequate answer",
        classify_answer(_adequate_for(q1), q1) == "adequate",
    )
    record(
        "very short/vague answer",
        classify_answer("Yeah I did that.", q1) == "shallow",
    )
    record(
        "clearly off-topic answer",
        classify_answer(
            "I spent the weekend baking sourdough and organizing my spice rack in great detail.",
            q1,
        )
        == "off_topic",
    )
    record(
        "bluff/evidence mismatch case",
        classify_answer(
            "I implemented the whole pipeline in totally_secret_kernel.py "
            "and shipped commit deadbeef1234567 myself last week.",
            _github_question(),
        )
        == "bluff",
    )


def test_timer() -> None:
    plan = _twelve_question_plan()
    box = {"now": 10.0}
    controller = InterviewController(plan, clock=lambda: _clock(box))
    record("timer starts at interview start", controller.interview_duration == 0)
    controller.start_interview()
    record(
        "timer starts at interview start",
        abs(controller.interview_duration - 0.0) < 0.001
        and controller.interview_start_time == 10.0,
        "second check",
    )
    box["now"] = 100.0
    record(
        "before 8 minutes -> normal progression",
        controller.interview_duration == 90
        and not controller.time_limit_reached()
        and _speak(controller, _adequate_for(controller.current_question() or {})) == "next"
        and controller.current_question_id() == "q2",
    )

    late = InterviewController(plan, clock=lambda: _clock(box))
    box["now"] = 0.0
    late.start_interview()
    box["now"] = float(INTERVIEW_LIMIT_SECONDS)
    late.note_question_asked()
    late.mark_candidate_speaking()
    record(
        "timer does not interrupt active candidate speech",
        late.time_limit_reached() and not late.should_wrap_up_now(),
    )
    late.mark_candidate_stopped()
    action = late.try_complete_answer(_adequate_for(late.current_question() or {}))
    first_wrap = late.begin_wrap_up()
    record(
        "at/after 480 seconds -> wrap-up",
        action == "wrap_up" and late.phase == "wrap_up" and first_wrap is False,
    )
    record(
        "no Q13 after timeout",
        late.current_question() is None
        and late.current_question_id() == ""
        and "q13" not in late.completed_ids,
    )
    record(
        "wrap-up generated exactly once",
        late.begin_wrap_up() is False and late.phase == "wrap_up",
    )


def test_regression_hooks() -> None:
    import agent

    logging_src = inspect.getsource(agent._attach_turn_logging)
    model_src = inspect.getsource(agent._realtime_model)
    flow_src = inspect.getsource(agent._attach_linear_flow)
    session_src = inspect.getsource(agent.interview_session)
    record(
        "barge-in code unchanged",
        "[INTERRUPT] Agent interrupted" in logging_src
        and "try_complete_answer" not in logging_src,
    )
    record(
        "Gemini / LiveKit realtime config unchanged",
        'voice="Puck"' in model_src
        and "SessionResumptionConfig" in model_src
        and "room_io.AudioInputOptions()" in session_src,
    )
    record(
        "follow-up path does not skip the question id",
        "follow_up" in flow_src
        and "follow_up_instructions" in flow_src
        and "start_interview" in session_src,
    )


def main() -> int:
    print("=== Phase 3 Slice 3 checks ===")
    print("--- Slice 1 ---")
    test_plan_gate()
    test_disk_plan_and_briefing()
    print("--- Slice 2 ---")
    test_linear_controller()
    test_duplicate_and_wrap_guard()
    test_q2_briefing_isolation()
    print("--- Slice 3 ---")
    test_follow_up_controller()
    test_classifier()
    test_timer()
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
