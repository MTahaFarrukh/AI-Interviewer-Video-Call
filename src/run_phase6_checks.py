"""Offline checks for Phase 6: live interview SQLite persistence and recovery."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from realtime.controller import INTERVIEW_LIMIT_SECONDS, InterviewController
from realtime.evaluate_interview import GO_MIN_FIT, GO_MIN_OVERALL, GO_MIN_TECH, evaluate_interview
from realtime.report import generate_report
from realtime.store import InterviewStore, interview_status_for
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
    _adequate_for,
    _shallow,
    test_classifier,
    test_follow_up_controller,
    test_regression_hooks,
    test_timer,
)
from run_phase3_slice4_checks import test_evaluation, test_slice4_hooks, test_transcript
from run_phase3_slice5_checks import test_report_generator, test_real_taha_report, test_slice5_hooks
from run_phase3_slice55_checks import (
    test_behavioral_and_speakability,
    test_github_grounding,
    test_plan_rules,
    test_slice55_hooks,
)


def _speak(controller: InterviewController, text: str, event_id: str = "") -> str:
    controller.note_question_asked()
    controller.mark_candidate_speaking()
    return controller.try_complete_answer(text, event_id=event_id)


def test_sqlite_store() -> None:
    plan = _twelve_question_plan()
    plan["candidate"] = {"name": "Muhammad Taha Farrukh"}
    plan["job"] = {"role": "Junior AI Engineer", "company": "Northwind Labs"}
    with tempfile.TemporaryDirectory() as tmp:
        store = InterviewStore(Path(tmp) / "interview.sqlite")
        iid = store.create_interview(
            "int-1",
            candidate="Muhammad Taha Farrukh",
            role="Junior AI Engineer",
            company="Northwind Labs",
        )
        created = store.get_interview(iid)
        record(
            "create interview",
            created is not None
            and created["status"] == "created"
            and created["candidate"] == "Muhammad Taha Farrukh",
        )

        saved = []

        def persist(controller: InterviewController) -> None:
            saved.append(1)
            store.save_from_controller(iid, controller, candidate="Muhammad Taha Farrukh")

        controller = InterviewController(plan, persist=persist)
        q1 = str((controller.current_question() or {}).get("question") or "")
        controller.start_interview()
        store.save_from_controller(iid, controller, status="running")
        record("persist state", store.get_interview(iid)["status"] == "running")

        controller.record_interviewer_turn(q1, "question")
        _speak(controller, _shallow(), event_id="evt-1")
        row = store.get_interview(iid)
        record("update state", row["follow_up_count"] == 1 and row["current_question_id"] == "q1")
        record(
            "persist transcript turn",
            len(store.get_transcript(iid)) >= 2
            and any(t["speaker"] == "candidate" for t in store.get_transcript(iid)),
        )

        reloaded = InterviewStore(Path(tmp) / "interview.sqlite").get_interview(iid)
        record("reload interview", reloaded is not None and reloaded["interview_id"] == iid)
        record(
            "reload transcript",
            len(reloaded["transcript"]) == len(controller.get_transcript()),
        )
        record("preserve follow_up_count", reloaded["follow_up_count"] == 1)
        record("preserve current question", reloaded["current_question_id"] == "q1")
        record("preserve status", reloaded["status"] in {"running", "partial", "created"})


def test_disconnect_and_duplicates() -> None:
    plan = _twelve_question_plan()
    with tempfile.TemporaryDirectory() as tmp:
        store = InterviewStore(Path(tmp) / "interview.sqlite")
        iid = "int-disconnect"
        store.create_interview(iid, candidate="Muhammad Taha Farrukh")
        controller = InterviewController(
            plan,
            persist=lambda current: store.save_from_controller(iid, current),
        )
        controller.start_interview()
        controller.record_interviewer_turn("Q1?", "question")
        _speak(controller, _shallow(), event_id="same")
        before = len(store.get_transcript(iid))
        ignored = controller.try_complete_answer(_shallow(), event_id="same")
        record(
            "duplicate completed turn does not duplicate transcript",
            ignored == "ignore" and len(store.get_transcript(iid)) == before,
        )
        index_before = controller.index
        record(
            "duplicate event does not advance twice",
            controller.current_question_id() == "q1" and index_before == 0,
        )

        status = interview_status_for(controller, disconnected=True)
        store.save_from_controller(iid, controller, status=status)
        disk = InterviewStore(Path(tmp) / "interview.sqlite").get_interview(iid)
        record("disconnected interview remains on disk", disk is not None)
        record("partial status is preserved", disk["status"] == "partial")
        record(
            "transcript survives disconnect",
            len(disk["transcript"]) == before and disk["transcript"][0]["text"] == "Q1?",
        )


def test_completion_and_timer() -> None:
    plan = _twelve_question_plan()
    controller = InterviewController(plan)
    record(
        "12 questions never becomes Q13",
        len(controller.questions) == 12,
    )
    for i in range(12):
        q = controller.current_question() or {}
        controller.record_interviewer_turn(str(q.get("question") or f"q{i+1}"), "question")
        action = _speak(controller, _adequate_for(q), event_id=f"q{i+1}")
    record(
        "wrap-up after Q12",
        action == "wrap_up"
        and controller.phase == "wrap_up"
        and controller.current_question_id() == ""
        and "q13" not in controller.completed_ids,
    )
    with tempfile.TemporaryDirectory() as tmp:
        store = InterviewStore(Path(tmp) / "live.sqlite")
        store.create_interview("done")
        store.save_from_controller("done", controller, status="completed")
        record(
            "completed interview status is correct",
            store.get_interview("done")["status"] == "completed"
            and interview_status_for(controller) == "completed",
        )

    box = {"now": 0.0}
    late = InterviewController(plan, clock=lambda: box["now"])
    late.start_interview()
    late.note_question_asked()
    late.mark_candidate_speaking()
    box["now"] = float(INTERVIEW_LIMIT_SECONDS)
    record(
        "timer does not interrupt an active candidate response",
        late.time_limit_reached() and not late.should_wrap_up_now(),
    )
    late.mark_candidate_stopped()
    action = late.try_complete_answer(_adequate_for(late.current_question() or {}))
    record(
        "8-minute timer triggers wrap-up",
        action == "wrap_up" and late.phase == "wrap_up",
    )


def test_report_from_store() -> None:
    from config import QUESTION_PLAN_PATH
    from prep.io import read_json

    plan = read_json(QUESTION_PLAN_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        store = InterviewStore(Path(tmp) / "interview.sqlite")
        iid = "int-report"
        store.create_interview(iid, candidate="Muhammad Taha Farrukh")
        controller = InterviewController(
            plan,
            persist=lambda current: store.save_from_controller(iid, current),
        )
        q1 = str((plan.get("questions") or [{}])[0].get("question") or "Q1")
        controller.record_interviewer_turn(q1, "question")
        _speak(controller, "I used recursive chunking with overlap because retrieval quality dropped on short docs.", event_id="a1")
        store.save_from_controller(iid, controller, status="partial")
        transcript = store.get_transcript(iid)
        result = evaluate_interview(plan, transcript)
        record(
            "persisted transcript can feed existing evaluator",
            result.get("recommendation") in {"GO", "NO_GO", "REVIEW"}
            and result.get("candidate", {}).get("name") == "Muhammad Taha Farrukh",
        )
        record(
            "existing evaluation thresholds unchanged",
            GO_MIN_OVERALL == 70 and GO_MIN_FIT == 60 and GO_MIN_TECH == 60,
        )
        report = generate_report(plan, transcript, result)
        record(
            "existing report generation still works",
            report.get("interview_status") == "partial"
            and (report.get("decision") or {}).get("recommendation") == result.get("recommendation"),
        )
        from generate_report import main as report_cli

        eval_path = Path(tmp) / "evaluation.json"
        out_json = Path(tmp) / "report.json"
        out_md = Path(tmp) / "report.md"
        code = report_cli(
            [
                "--interview-id",
                iid,
                "--store",
                str(store.path),
                "--plan",
                str(QUESTION_PLAN_PATH),
                "--evaluation",
                str(eval_path),
                "--out-json",
                str(out_json),
                "--out-md",
                str(out_md),
            ]
        )
        record(
            "report CLI loads persisted interview",
            code == 0 and out_json.is_file() and out_md.is_file(),
        )


def test_phase6_hooks() -> None:
    import agent
    import generate_report as generate_report_cli
    import realtime.evaluate_interview as evaluator

    flow_src = inspect.getsource(agent._attach_linear_flow)
    session_src = inspect.getsource(agent.interview_session)
    model_src = inspect.getsource(agent._realtime_model)
    eval_src = inspect.getsource(evaluator.evaluate_interview)
    cli_src = inspect.getsource(generate_report_cli.main)
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    frontend_names = sorted(p.name for p in frontend_dir.iterdir() if p.is_file())
    record(
        "evaluator is not invoked on the audio path",
        "evaluate_interview" not in flow_src and "evaluate_interview" not in session_src,
    )
    record(
        "disconnect persistence is logged",
        "[INTERVIEW] disconnected" in session_src
        and "interview_status_for" in session_src
        and "[INTERVIEW] store_path=" in session_src,
    )
    record(
        "Gemini 2.5 / LiveKit realtime config unchanged",
        'voice="Puck"' in model_src
        and "SessionResumptionConfig" in model_src
        and "room_io.AudioInputOptions()" in session_src,
    )
    record(
        "evaluator scoring body unchanged",
        "0.20 * dimensions[\"jd_resume_fit\"]" in eval_src,
    )
    record(
        "report CLI accepts --interview-id",
        "--interview-id" in cli_src and "InterviewStore" in cli_src,
    )
    record(
        "frontend unchanged",
        frontend_names == ["app.js", "index.html", "styles.css"],
    )


def main() -> int:
    print("=== Phase 6 checks ===")
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
    print("--- Slice 5 ---")
    test_report_generator()
    test_real_taha_report()
    print("--- Slice 5.5 ---")
    test_github_grounding()
    test_behavioral_and_speakability()
    test_plan_rules()
    print("--- Phase 6 ---")
    test_sqlite_store()
    test_disconnect_and_duplicates()
    test_completion_and_timer()
    test_report_from_store()
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    test_slice4_hooks()
    test_slice5_hooks()
    test_slice55_hooks()
    test_phase6_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
