"""Offline checks for Phase 3 Slice 2: linear Q1..Q12 then wrap-up."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from plan_loader import compact_briefing, turn_instructions, wrap_up_instructions
from realtime.controller import InterviewController
from run_phase3_slice1_checks import (
    RESULTS,
    record,
    test_disk_plan_and_briefing,
    test_phase1_realtime_unchanged,
    test_plan_gate,
)

from config import QUESTION_PLAN_PATH
from plan_loader import load_approved_plan


def _twelve_question_plan() -> dict:
    questions = []
    for i in range(1, 13):
        questions.append(
            {
                "id": f"q{i}",
                "category": "Technical" if i < 10 else "Behavioral",
                "question": f"UNIQUE_QUESTION_TEXT_FOR_Q{i} about skill {i}.",
                "competency": f"competency-{i}",
                "rationale": f"rationale-{i}",
                "expected_evidence": f"evidence-{i}",
                "source": "resume",
                "source_reference": f"ref-{i}",
            }
        )
    return {
        "candidate": {"name": "Test Candidate"},
        "job": {"role": "Junior AI Engineer", "company": "Northwind Labs"},
        "approval_status": "approved",
        "questions": questions,
    }


def _adequate_answer(controller: InterviewController) -> str:
    q = (controller.current_question() or {}).get("question") or "this topic"
    return (
        f"I can answer {q} I used a concrete example with validation, tests, "
        f"and a clear trade-off because that made the design easier to debug."
    )


def _answer_once(controller: InterviewController) -> str:
    text = _adequate_answer(controller)
    controller.note_question_asked()
    controller.mark_candidate_speaking()
    return controller.try_complete_answer(text)


def test_linear_controller() -> None:
    plan = _twelve_question_plan()
    controller = InterviewController(plan)
    record(
        "controller starts at Q1",
        controller.phase == "intro"
        and controller.index == 0
        and controller.current_question_id() == "q1"
        and controller.completed_ids == [],
    )

    nxt = controller.advance()
    record(
        "advance Q1 -> Q2",
        nxt is not None
        and controller.current_question_id() == "q2"
        and controller.phase == "question"
        and controller.completed_ids == ["q1"],
    )

    while controller.current_question_id() != "q11":
        controller.advance()
    nxt = controller.advance()
    record(
        "advance Q11 -> Q12",
        nxt is not None
        and controller.current_question_id() == "q12"
        and controller.completed_ids[-1] == "q11",
    )

    nxt = controller.advance()
    record(
        "advance Q12 -> wrap_up",
        nxt is None
        and controller.phase == "wrap_up"
        and controller.current_question() is None
        and controller.current_question_id() == ""
        and controller.completed_ids[-1] == "q12",
        ",".join(controller.completed_ids),
    )

    stuck = controller.advance()
    record(
        "cannot advance past Q12",
        stuck is None
        and controller.phase == "wrap_up"
        and controller.current_question() is None
        and controller.completed_ids.count("q12") == 1
        and "q13" not in controller.completed_ids,
    )
    record(
        "completed question IDs are tracked",
        controller.completed_ids == [f"q{i}" for i in range(1, 13)],
    )


def test_duplicate_and_wrap_guard() -> None:
    plan = _twelve_question_plan()
    controller = InterviewController(plan)
    first = _answer_once(controller)
    record(
        "completed candidate turn advances Q1 -> Q2",
        first == "next" and controller.current_question_id() == "q2",
    )
    duplicate = controller.try_complete_answer()
    second_duplicate = controller.try_complete_answer()
    record(
        "duplicate completion event does not skip questions",
        duplicate == "ignore"
        and second_duplicate == "ignore"
        and controller.current_question_id() == "q2"
        and controller.completed_ids == ["q1"],
    )

    speaking_only = InterviewController(plan)
    speaking_only.note_question_asked()
    speaking_only.mark_candidate_speaking()
    # interruption / start-speaking must not complete by itself
    record(
        "speaking start alone does not advance",
        speaking_only.current_question_id() == "q1"
        and speaking_only.completed_ids == [],
    )

    linear = InterviewController(plan)
    actions = []
    for _ in range(12):
        actions.append(_answer_once(linear))
    extra = _answer_once(linear)
    extra_advance = linear.advance()
    record(
        "wrap-up does not attempt Q13",
        actions[-1] == "wrap_up"
        and extra == "ignore"
        and extra_advance is None
        and linear.phase == "wrap_up"
        and linear.current_question() is None
        and "q13" not in linear.completed_ids
        and wrap_up_instructions("Taha").find("q13") == -1
        and "Do not ask another interview question" in wrap_up_instructions(),
        str(actions[-1]),
    )


def test_q2_briefing_isolation() -> None:
    plan = load_approved_plan(QUESTION_PLAN_PATH) or _twelve_question_plan()
    questions = [q for q in (plan.get("questions") or []) if isinstance(q, dict)]
    if len(questions) < 3:
        plan = _twelve_question_plan()
        questions = plan["questions"]
    q2 = questions[1]
    briefing = compact_briefing(plan, str(q2.get("id") or "q2"))
    blob = json.dumps(briefing, ensure_ascii=False)
    q2_text = str(q2.get("question") or "")
    leaked = [
        str(q.get("question") or "")
        for q in questions[2:]
        if q.get("question") and str(q.get("question")) in blob
    ]
    record(
        "compact briefing for Q2 contains Q2 only",
        briefing.get("question_id") == str(q2.get("id") or "q2")
        and briefing.get("question") == q2_text
        and q2_text in blob,
        str(briefing.get("question_id")),
    )
    record(
        "Q2 briefing does not leak Q3-Q12",
        not leaked and "questions" not in briefing,
        f"leaked={len(leaked)}",
    )
    instructions = turn_instructions(briefing)
    later = [str(q.get("question") or "") for q in questions[2:] if q.get("question")]
    leaked_instr = [text for text in later if text and text in instructions]
    record(
        "Q2 turn instructions ask only Q2",
        q2_text in instructions
        and "Do not skip ahead" in instructions
        and not leaked_instr,
    )


def test_agent_hooks_unchanged() -> None:
    import agent

    logging_src = inspect.getsource(agent._attach_turn_logging)
    model_src = inspect.getsource(agent._realtime_model)
    session_src = inspect.getsource(agent.interview_session)
    flow_src = inspect.getsource(agent._attach_linear_flow)
    record(
        "Slice 2 uses completed user conversation items",
        "role != \"user\"" in flow_src
        and "try_complete_answer" in flow_src
        and "[PLAN] completed" in flow_src
        and "[PLAN] wrap_up" in flow_src,
    )
    record(
        "interruption is not treated as completion",
        "mark_candidate_speaking" in flow_src
        and "try_complete_answer" not in logging_src
        and "[INTERRUPT]" in logging_src,
    )
    record(
        "_realtime_model body unchanged",
        'voice="Puck"' in model_src
        and "SessionResumptionConfig" in model_src
        and "trigger_tokens=25600" in model_src,
    )
    record(
        "_attach_turn_logging body unchanged",
        "[LATENCY] candidate_stop_to_agent_audio_ms=" in logging_src
        and "[INTERRUPT] Agent interrupted" in logging_src,
    )
    record(
        "Slice 1 opening still uses approved Q1",
        "opening_instructions" in session_src
        and "note_question_asked" in session_src,
    )


def main() -> int:
    print("=== Phase 3 Slice 2 checks ===")
    print("--- Slice 1 plan gate ---")
    test_plan_gate()
    test_disk_plan_and_briefing()
    print("--- Slice 2 linear flow ---")
    test_linear_controller()
    test_duplicate_and_wrap_guard()
    test_q2_briefing_isolation()
    print("--- Phase 1 / realtime ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
