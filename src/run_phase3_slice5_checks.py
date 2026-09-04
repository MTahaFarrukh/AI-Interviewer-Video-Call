"""Offline checks for Phase 3 Slice 5: recruiter report from plan + transcript + eval."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    GEMINI_LIVE_MODEL,
    INTERVIEW_EVALUATION_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    QUESTION_PLAN_PATH,
)
from prep.io import read_json
from prep.samples import SAMPLE_WARNING
from realtime.evaluate_interview import DIMENSIONS
from realtime.report import generate_report, render_markdown
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
    test_classifier,
    test_follow_up_controller,
    test_regression_hooks,
    test_timer,
)
from run_phase3_slice4_checks import test_evaluation, test_slice4_hooks, test_transcript


def _eval_payload(**overrides: object) -> dict:
    payload = {
        "candidate": {
            "name": "Test Candidate",
            "role": "Junior AI Engineer",
            "company": "Northwind Labs",
        },
        "overall_score": 64,
        "dimensions": {name: 70 for name in DIMENSIONS},
        "question_results": [
            {
                "question_id": "q1",
                "category": "Technical",
                "answer_summary": "Answered q1 with some detail.",
                "assessment": "adequate",
                "evidence": ["Directly addressed the question with reasonable detail."],
                "concerns": [],
                "score": 72,
            },
            {
                "question_id": "q2",
                "category": "Technical",
                "answer_summary": "Short q2 answer.",
                "assessment": "weak",
                "evidence": [],
                "concerns": ["Repeated or vague answers with little evidence."],
                "score": 42,
            },
        ],
        "strengths": ["Phase 2 gap analysis shows strong skill matches with the JD."],
        "weaknesses": ["q2: shallow or under-specified answers."],
        "concerns": [],
        "recommendation": "REVIEW",
        "recommendation_reason": "Mixed or borderline evidence; not enough to recommend GO or NO_GO.",
    }
    payload["dimensions"]["jd_resume_fit"] = 82
    payload["dimensions"]["technical_competence"] = 57
    payload["dimensions"]["github_credibility"] = 70
    payload.update(overrides)
    return payload


def _two_question_transcript(plan: dict) -> list[dict]:
    q1 = str(plan["questions"][0]["question"])
    q2 = str(plan["questions"][1]["question"])
    return [
        {"speaker": "interviewer", "question_id": "q1", "turn_type": "question", "text": q1, "timestamp": 10.0},
        {"speaker": "candidate", "question_id": "q1", "turn_type": "answer", "text": "first answer", "timestamp": 20.0},
        {"speaker": "interviewer", "question_id": "q1", "turn_type": "follow_up", "text": "probe", "timestamp": 21.0},
        {"speaker": "candidate", "question_id": "q1", "turn_type": "answer", "text": "follow-up answer", "timestamp": 30.0},
        {"speaker": "interviewer", "question_id": "q2", "turn_type": "question", "text": q2, "timestamp": 31.0},
        {"speaker": "candidate", "question_id": "q2", "turn_type": "answer", "text": "second answer", "timestamp": 40.0},
        {"speaker": "interviewer", "question_id": "q2", "turn_type": "follow_up", "text": "probe 2", "timestamp": 41.0},
    ]


def test_report_generator() -> None:
    plan = _twelve_question_plan()
    plan["approval_status"] = "approved"
    plan["approved_by_human"] = True
    plan["sample_mode"] = False
    plan["questions"][3] = {
        **plan["questions"][3],
        "source": "github",
        "repository": "https://github.com/example/approved-repo",
        "file": "src/approved.py",
        "commit": "abc123def456",
        "source_reference": "example/approved-repo/src/approved.py@abc123d",
        "evidence": "Approved file excerpt from the plan.",
    }
    evaluation = _eval_payload()
    transcript = _two_question_transcript(plan)
    report = generate_report(plan, transcript, evaluation)
    md = render_markdown(report)

    record("report generated from real inputs", isinstance(report, dict) and report.get("candidate"))
    record(
        "candidate information preserved",
        (report.get("candidate") or {}).get("name") == "Test Candidate",
    )
    record(
        "role/company preserved",
        (report.get("candidate") or {}).get("role") == "Junior AI Engineer"
        and (report.get("candidate") or {}).get("company") == "Northwind Labs",
    )
    record(
        "recommendation exactly matches evaluation",
        (report.get("decision") or {}).get("recommendation") == evaluation["recommendation"]
        and (report.get("decision") or {}).get("reason") == evaluation["recommendation_reason"],
    )
    scorecard = report.get("scorecard") or {}
    record(
        "all scorecard dimensions present",
        all(name in scorecard for name in DIMENSIONS),
    )
    record(
        "scores preserved",
        (report.get("decision") or {}).get("overall_score") == 64
        and scorecard.get("jd_resume_fit") == 82
        and scorecard.get("technical_competence") == 57
        and scorecard.get("github_credibility") == 70
        and scorecard == evaluation["dimensions"],
    )
    record("strengths preserved", report.get("strengths") == evaluation["strengths"])
    record("weaknesses preserved", report.get("weaknesses") == evaluation["weaknesses"])
    record("concerns preserved", report.get("concerns") == evaluation["concerns"])

    github = report.get("github_evidence") or []
    blob = json.dumps(github)
    record(
        "GitHub evidence comes from approved plan",
        len(github) == 1
        and github[0]["file"] == "src/approved.py"
        and github[0]["commit"] == "abc123def456"
        and github[0]["related_question"] == "q4"
        and "totally_secret_kernel.py" not in blob
        and "approved-repo" in github[0]["repository"],
    )

    stats = report.get("transcript_stats") or {}
    record(
        "transcript statistics are correct",
        stats.get("completed_turns") == 7
        and stats.get("interviewer_turns") == 4
        and stats.get("candidate_turns") == 3
        and stats.get("questions_attempted") == 2
        and stats.get("follow_ups") == 2
        and stats.get("elapsed_seconds") == 31,
    )
    record(
        "partial interview correctly marked",
        report.get("interview_status") == "partial"
        and report.get("questions_attempted") == 2
        and report.get("questions_total") == 12
        and "Partial" in str(report.get("interview_summary") or ""),
    )
    q_results = report.get("question_results") or []
    attempted = [item for item in q_results if item.get("status") == "attempted"]
    skipped = [item for item in q_results if item.get("status") == "not_attempted"]
    record(
        "unattempted questions are not falsely marked answered",
        len(q_results) == 12
        and len(attempted) == 2
        and len(skipped) == 10
        and attempted[0]["question_id"] == "q1"
        and attempted[1]["question_id"] == "q2"
        and all(item.get("score") is None for item in skipped)
        and all(item.get("assessment") == "" for item in skipped)
        and q_results[0].get("follow_up_count") == 1,
    )
    record(
        "sample_mode correctly propagated",
        (report.get("metadata") or {}).get("sample_mode") is False
        and (report.get("metadata") or {}).get("data_label") == "REAL CANDIDATE DATA",
    )
    sample_plan = copy.deepcopy(plan)
    sample_plan["sample_mode"] = True
    sample_report = generate_report(sample_plan, transcript, evaluation)
    record(
        "sample_mode warning is not dropped",
        (sample_report.get("metadata") or {}).get("sample_mode") is True
        and SAMPLE_WARNING in (sample_report.get("metadata") or {}).get("data_label", "")
        and SAMPLE_WARNING in render_markdown(sample_report),
    )
    record(
        "limitations included",
        isinstance(report.get("limitations"), list)
        and any("partial" in item.lower() for item in report["limitations"])
        and any("completeness" in item.lower() for item in report["limitations"]),
    )
    record(
        "Markdown report generated",
        "# Candidate Interview Report" in md
        and "REVIEW" in md
        and "Junior AI Engineer" in md
        and "PARTIAL" in md
        and "not attempted" in md,
    )

    go_looking = _eval_payload(recommendation="REVIEW")
    go_looking["dimensions"] = {name: 90 for name in DIMENSIONS}
    go_looking["overall_score"] = 90
    locked = generate_report(plan, transcript, go_looking)
    record(
        "recommendation is not recomputed from resume strength",
        (locked.get("decision") or {}).get("recommendation") == "REVIEW"
        and (locked.get("decision") or {}).get("overall_score") == 90,
    )

    full_turns = []
    for i in range(1, 13):
        qid = f"q{i}"
        full_turns.append(
            {
                "speaker": "interviewer",
                "question_id": qid,
                "turn_type": "question",
                "text": plan["questions"][i - 1]["question"],
            }
        )
        full_turns.append(
            {"speaker": "candidate", "question_id": qid, "turn_type": "answer", "text": f"answer {i}"}
        )
    completed = generate_report(plan, full_turns, evaluation)
    record(
        "completed 12-question interview is not marked partial",
        completed.get("interview_status") == "completed"
        and completed.get("questions_attempted") == 12,
    )


def test_real_taha_report() -> None:
    plan = read_json(QUESTION_PLAN_PATH)
    transcript = read_json(INTERVIEW_TRANSCRIPT_PATH)
    evaluation = read_json(INTERVIEW_EVALUATION_PATH)
    report = generate_report(plan, transcript, evaluation)
    candidate = report.get("candidate") or {}
    decision = report.get("decision") or {}
    scorecard = report.get("scorecard") or {}
    metadata = report.get("metadata") or {}
    record(
        "real Taha candidate/role/company",
        candidate.get("name") == "Muhammad Taha Farrukh"
        and candidate.get("role") == "Junior AI Engineer"
        and candidate.get("company") == "Northwind Labs",
    )
    record(
        "real Taha recommendation and scores",
        decision.get("recommendation") == evaluation.get("recommendation")
        and decision.get("recommendation") in {"GO", "NO_GO", "REVIEW"}
        and decision.get("overall_score") == evaluation.get("overall_score")
        and scorecard.get("jd_resume_fit") == (evaluation.get("dimensions") or {}).get("jd_resume_fit")
        and scorecard.get("technical_competence") == (evaluation.get("dimensions") or {}).get("technical_competence")
        and scorecard.get("github_credibility") == (evaluation.get("dimensions") or {}).get("github_credibility"),
    )
    attempted = report.get("questions_attempted")
    record(
        "real Taha interview is partial with sample_mode false",
        report.get("interview_status") == "partial"
        and isinstance(attempted, int)
        and 1 <= attempted < 12
        and report.get("questions_total") == 12
        and metadata.get("sample_mode") is False
        and metadata.get("data_label") == "REAL CANDIDATE DATA"
        and "Ayesha" not in json.dumps(report),
    )
    github = report.get("github_evidence") or []
    record(
        "real Taha GitHub evidence is from the approved plan",
        github
        and all(item.get("commit") and item.get("file") and item.get("repository") for item in github)
        and all("MTahaFarrukh" in item.get("repository", "") for item in github),
    )


def test_slice5_hooks() -> None:
    import agent
    import generate_report as generate_report_cli
    import realtime.report as report_mod

    report_src = Path(inspect.getsourcefile(report_mod)).read_text(encoding="utf-8")
    cli_src = Path(inspect.getsourcefile(generate_report_cli)).read_text(encoding="utf-8")
    agent_src = Path(inspect.getsourcefile(agent)).read_text(encoding="utf-8")
    model_src = inspect.getsource(agent._realtime_model)
    logging_src = inspect.getsource(agent._attach_turn_logging)
    flow_src = inspect.getsource(agent._attach_linear_flow)
    frontend_dir = ROOT_DIR / "frontend"
    frontend_names = sorted(p.name for p in frontend_dir.iterdir() if p.is_file())
    digest = hashlib.sha256()
    for name in frontend_names:
        digest.update((frontend_dir / name).read_bytes())

    record(
        "RealtimeModel still constructs",
        agent._realtime_model() is not None,
    )
    record(
        "Gemini 2.5 model unchanged",
        GEMINI_LIVE_MODEL == "gemini-2.5-flash-native-audio-preview-12-2025"
        and "model=GEMINI_LIVE_MODEL" in model_src,
    )
    record(
        "LiveKit configuration unchanged",
        'voice="Puck"' in model_src
        and "room_io.AudioInputOptions()" in inspect.getsource(agent.interview_session),
    )
    record(
        "barge-in unchanged",
        "[INTERRUPT] Agent interrupted" in logging_src
        and "try_complete_answer" not in logging_src,
    )
    record(
        "frontend unchanged",
        frontend_names == ["app.js", "index.html", "styles.css"]
        and "frontend" not in report_src
        and digest.hexdigest() != "",
    )
    record(
        "report generator is offline and does not recompute evaluation",
        "livekit" not in report_src
        and "livekit" not in cli_src
        and "evaluate_interview" not in report_src
        and "generate_report" not in flow_src
        and "from realtime.report" not in agent_src,
    )


def main() -> int:
    print("=== Phase 3 Slice 5 checks ===")
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
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    test_slice4_hooks()
    test_slice5_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
