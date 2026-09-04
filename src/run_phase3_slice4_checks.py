"""Offline checks for Phase 3 Slice 4: transcript + post-interview evaluation."""

from __future__ import annotations

import copy
import inspect
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from realtime.controller import InterviewController
from realtime.evaluate_interview import DIMENSIONS, evaluate_interview, recommend
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
from run_phase3_slice3_checks import (
    _shallow,
    test_classifier,
    test_follow_up_controller,
    test_regression_hooks,
    test_timer,
)


def _speak(controller: InterviewController, text: str, event_id: str = "") -> str:
    controller.note_question_asked()
    controller.mark_candidate_speaking()
    return controller.try_complete_answer(text, event_id=event_id)


def test_transcript() -> None:
    plan = _twelve_question_plan()
    controller = InterviewController(plan)
    q1 = str((controller.current_question() or {}).get("question") or "")
    controller.record_interviewer_turn(q1, "question")
    record(
        "interviewer turn captured",
        controller.get_transcript()
        and controller.get_transcript()[0]["speaker"] == "interviewer"
        and controller.get_transcript()[0]["turn_type"] == "question"
        and controller.get_transcript()[0]["question_id"] == "q1",
    )

    _speak(controller, _shallow(), event_id="evt-1")
    answers = [t for t in controller.get_transcript() if t["speaker"] == "candidate"]
    record(
        "candidate answer captured",
        len(answers) == 1 and answers[0]["text"] == _shallow(),
    )
    record(
        "question_id attached",
        answers[0]["question_id"] == "q1",
    )

    _speak(controller, _shallow(), event_id="evt-2")
    q1_answers = [
        t for t in controller.get_transcript() if t["speaker"] == "candidate" and t["question_id"] == "q1"
    ]
    record(
        "follow-up answer keeps same question_id",
        len(q1_answers) == 2
        and controller.current_question_id() == "q1"
        and all(item["question_id"] == "q1" for item in q1_answers),
    )

    before = len(controller.get_transcript())
    ignored = controller.try_complete_answer(_shallow(), event_id="evt-2")
    record(
        "duplicate candidate event does not duplicate transcript",
        ignored == "ignore" and len(controller.get_transcript()) == before,
    )

    noisy = InterviewController(plan)
    noisy.record_interviewer_turn(q1, "question")
    noisy.note_question_asked()
    noisy.mark_candidate_speaking()
    # interruption / start-speaking is not a completed answer
    record(
        "interruption does not create fake candidate answer",
        noisy.current_question_id() == "q1"
        and not any(t["speaker"] == "candidate" for t in noisy.get_transcript()),
    )
    retrieved = noisy.get_transcript()
    retrieved.append({"speaker": "candidate", "text": "mutated"})
    record(
        "transcript can be retrieved from controller",
        noisy.get_transcript() != retrieved
        and all(t["speaker"] == "interviewer" for t in noisy.get_transcript()),
    )


def _strong_q1(plan: dict) -> str:
    q = str(plan["questions"][0]["question"])
    return (
        f"For {q} I parsed documents, used chunk size 500 with overlap 50, "
        f"generated embeddings, stored vectors in Chroma, and retrieved top-k "
        f"passages because that improved faithfulness on 40 gold questions. "
        f"I also logged retrieval misses so I could debug empty context windows."
    )


def test_evaluation() -> None:
    plan = _twelve_question_plan()
    plan["candidate"] = {"name": "Test Candidate"}
    plan["job"] = {"role": "Junior AI Engineer", "company": "Northwind Labs"}
    plan["gap_analysis"] = {
        "matched_skills": ["Python", "RAG", "FastAPI"],
        "missing_skills": [],
        "weak_matches": [],
        "strong_matches": ["RAG pipelines"],
    }
    q1_text = str(plan["questions"][0]["question"])
    transcript = [
        {"speaker": "interviewer", "question_id": "q1", "turn_type": "question", "text": q1_text},
        {"speaker": "candidate", "question_id": "q1", "turn_type": "answer", "text": _strong_q1(plan)},
        {
            "speaker": "interviewer",
            "question_id": "q2",
            "turn_type": "question",
            "text": str(plan["questions"][1]["question"]),
        },
        {
            "speaker": "candidate",
            "question_id": "q2",
            "turn_type": "answer",
            "text": _adequate_answer.__wrapped__ if False else (
                f"I can answer {plan['questions'][1]['question']} I used a concrete example "
                f"with validation, tests, and a clear trade-off because that made debugging easier."
            ),
        },
    ]
    snapshot = copy.deepcopy(transcript)
    result = evaluate_interview(plan, transcript)
    record(
        "valid transcript produces structured evaluation",
        isinstance(result, dict) and result.get("recommendation") in {"GO", "NO_GO", "REVIEW"},
    )
    dims = result.get("dimensions") or {}
    record(
        "all required dimensions exist",
        all(name in dims for name in DIMENSIONS),
        ",".join(DIMENSIONS),
    )
    record(
        "scores are 0-100",
        0 <= int(result.get("overall_score") or -1) <= 100
        and all(0 <= int(dims[name]) <= 100 for name in DIMENSIONS),
    )
    record(
        "question results exist",
        isinstance(result.get("question_results"), list) and result["question_results"],
    )
    record(
        "strengths/weaknesses/concerns exist",
        "strengths" in result and "weaknesses" in result and "concerns" in result,
    )
    record(
        "recommendation is only GO/NO_GO/REVIEW",
        result.get("recommendation") in {"GO", "NO_GO", "REVIEW"},
        str(result.get("recommendation")),
    )

    go_dims = {name: 80 for name in DIMENSIONS}
    no_go_dims = {name: 20 for name in DIMENSIONS}
    review_dims = {name: 58 for name in DIMENSIONS}
    rec_go, _ = recommend(go_dims, [])
    rec_no, _ = recommend(no_go_dims, ["serious unsupported GitHub claim"])
    rec_rev, _ = recommend(review_dims, [])
    record(
        "recommendation rule is deterministic/testable",
        rec_go == "GO" and rec_no == "NO_GO" and rec_rev == "REVIEW",
        f"{rec_go}/{rec_no}/{rec_rev}",
    )

    github_plan = copy.deepcopy(plan)
    github_plan["questions"][0] = {
        **github_plan["questions"][0],
        "id": "q4",
        "source": "github",
        "file": "libs/core/langchain_core/_api/internal.py",
        "commit": "a92c032ff69ca6ec84451f8e13af1109d1a4f9ca",
        "repository": "https://github.com/langchain-ai/langchain",
        "question": "Explain inspect usage in internal.py",
    }
    bluff_transcript = [
        {"speaker": "interviewer", "question_id": "q4", "turn_type": "question", "text": "Explain inspect"},
        {
            "speaker": "candidate",
            "question_id": "q4",
            "turn_type": "answer",
            "text": "I implemented the whole pipeline in totally_secret_kernel.py and shipped commit deadbeef1234567.",
        },
    ]
    bluff_eval = evaluate_interview(github_plan, bluff_transcript)
    blob = json.dumps(bluff_eval)
    record(
        "GitHub evidence comes only from approved plan",
        "unsupported" in blob.lower()
        and "totally_secret_kernel.py" not in json.dumps(github_plan)
        and bluff_eval.get("recommendation") == "NO_GO",
        str(bluff_eval.get("recommendation")),
    )

    controller = InterviewController(plan)
    before_index = controller.index
    before_phase = controller.phase
    evaluate_interview(plan, snapshot)
    record(
        "evaluator does not modify controller state",
        controller.index == before_index
        and controller.phase == before_phase
        and controller.get_transcript() == [],
    )
    record("fixture transcript is a list of turns", snapshot == transcript)


def test_slice4_hooks() -> None:
    import agent

    flow_src = inspect.getsource(agent._attach_linear_flow)
    logging_src = inspect.getsource(agent._attach_turn_logging)
    model_src = inspect.getsource(agent._realtime_model)
    record(
        "evaluator is not on the audio path",
        "evaluate_interview" not in flow_src
        and "evaluate_interview" not in logging_src
        and "evaluate_interview" not in model_src,
    )
    record(
        "transcript recorded from completed turns only",
        "record_interviewer_turn" in flow_src
        and "try_complete_answer" in flow_src
        and "mark_candidate_speaking" in flow_src,
    )


def main() -> int:
    print("=== Phase 3 Slice 4 checks ===")
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
    print("--- Slice 4 ---")
    test_transcript()
    test_evaluation()
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    test_slice4_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
