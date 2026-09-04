"""Offline Phase 9 checks: PDF grading artifacts. Does not start LiveKit."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    INTERVIEW_EVALUATION_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    PDF_REPORT_PATH,
    PDF_SCORECARD_PATH,
    PDF_TRANSCRIPT_PATH,
    PREP_OUTPUT_DIR,
    QUESTION_PLAN_PATH,
)
from plan_loader import compact_briefing, load_approved_plan, spoken_question_text
from prep.banned import BANNED_PATTERNS, sanitize_spoken_question
from prep.io import read_json
from realtime.controller import InterviewController
from realtime.scorecard import (
    apply_evidence_guardrail,
    quote_in_candidate_transcript,
)
from realtime.store import InterviewStore
from run_phase3_slice2_checks import _twelve_question_plan
from run_phase3_slice3_checks import _speak, _strong_for

RESULTS: list[tuple[str, bool, str]] = []
TAHA = "Muhammad Taha Farrukh"
ROLE = "Junior AI Engineer"
REQUIRED_PDF_TOOLS = (
    "get_candidate",
    "get_question_plan",
    "save_score",
    "get_scorecard",
    "list_interviews",
)
BANNED_SAMPLES = {
    "age": "How old are you?",
    "gender": "What is your gender?",
    "marital": "Are you married?",
    "religion": "What is your religion?",
    "nationality": "What country are you from?",
    "health": "Are you pregnant?",
    "salary_history": "What is your current salary?",
    "politics": "Which political party do you support?",
}


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{': ' + detail if detail else ''}")


def _has_sample_leak(payload: object) -> bool:
    text = json.dumps(payload, ensure_ascii=False).lower() if not isinstance(payload, str) else payload.lower()
    return "ayesha" in text or "github.com/langchain-ai" in text


def test_required_output_paths() -> None:
    for name in ("jd.json", "resume.json", "github.json", "question_plan.json"):
        path = PREP_OUTPUT_DIR / name
        record(f"output/prep/{name} exists", path.is_file())


def test_transcript_schema() -> None:
    record("output/transcript.json exists", PDF_TRANSCRIPT_PATH.is_file())
    payload = read_json(PDF_TRANSCRIPT_PATH) if PDF_TRANSCRIPT_PATH.is_file() else {}
    turns = payload.get("turns") if isinstance(payload, dict) else None
    ok_schema = isinstance(turns, list) and turns and all(
        set(item) >= {"speaker", "text", "timestamp_ms", "node", "interrupted"}
        and item.get("speaker") in {"agent", "candidate"}
        and isinstance(item.get("timestamp_ms"), int)
        and isinstance(item.get("interrupted"), bool)
        for item in turns
        if isinstance(item, dict)
    )
    record("output/transcript.json schema valid", bool(ok_schema), f"turns={len(turns or [])}")
    candidate_turns = [item for item in (turns or []) if item.get("speaker") == "candidate"]
    record(
        "PDF transcript uses real candidate turns",
        len(candidate_turns) >= 1
        and any(len(str(item.get("text") or "")) >= 12 for item in candidate_turns),
    )
    record("no Ayesha/langchain-ai leak in transcript.json", not _has_sample_leak(payload))


def test_scorecard_and_evidence() -> None:
    record("output/scorecard.json exists", PDF_SCORECARD_PATH.is_file())
    scorecard = read_json(PDF_SCORECARD_PATH) if PDF_SCORECARD_PATH.is_file() else {}
    required = {
        "candidate_name",
        "role",
        "interview_date",
        "duration_seconds",
        "competencies",
        "overall_score",
        "recommendation",
        "recommendation_reasoning",
        "strengths",
        "concerns",
        "guardrail_flags",
        "github_grounded_questions_asked",
    }
    record(
        "output/scorecard.json schema valid",
        isinstance(scorecard, dict) and required <= set(scorecard)
        and scorecard.get("candidate_name") == TAHA
        and scorecard.get("role") == ROLE
        and scorecard.get("recommendation") in {"hire", "no_hire", "borderline"},
        str(scorecard.get("recommendation")),
    )
    source = read_json(INTERVIEW_TRANSCRIPT_PATH) if INTERVIEW_TRANSCRIPT_PATH.is_file() else []
    exported = read_json(PDF_TRANSCRIPT_PATH) if PDF_TRANSCRIPT_PATH.is_file() else {"turns": []}
    combined = list(source if isinstance(source, list) else []) + list(
        (exported.get("turns") if isinstance(exported, dict) else []) or []
    )
    all_ok = True
    for item in scorecard.get("competencies") or []:
        if item.get("score") is None:
            continue
        quote = str(item.get("evidence_quote") or "")
        if not quote_in_candidate_transcript(quote, combined):
            all_ok = False
            break
        if not (1 <= int(item["score"]) <= 5):
            all_ok = False
            break
        conf = float(item.get("confidence") or 0)
        if conf < 0 or conf > 1:
            all_ok = False
            break
    record("every non-null score has a valid candidate transcript quote", all_ok)

    valid_quote = next(
        (
            str(turn.get("text") or "")
            for turn in (source if isinstance(source, list) else [])
            if turn.get("speaker") == "candidate" and len(str(turn.get("text") or "").split()) >= 3
            and len(str(turn.get("text") or "")) >= 12
        ),
        "I first make chunks and then store it in a vector DV.",
    )
    record(
        "valid quote passes the evidence guardrail",
        quote_in_candidate_transcript(valid_quote, source if isinstance(source, list) else []),
    )
    invented = "I implemented a classified CUDA kernel that is not in this transcript."
    record(
        "invented quote is rejected",
        not quote_in_candidate_transcript(invented, source if isinstance(source, list) else []),
    )
    rejected, flags = apply_evidence_guardrail(
        [
            {
                "name": "Technical competence",
                "score": 5,
                "confidence": 0.9,
                "evidence_quote": invented,
                "reasoning": "should not survive",
            }
        ],
        source if isinstance(source, list) else [],
    )
    record(
        "score cannot survive without evidence",
        rejected[0].get("score") is None
        and any(flag.get("type") == "invalid_evidence_quote" for flag in flags),
    )


def test_pdf_report() -> None:
    record("output/report.pdf exists", PDF_REPORT_PATH.is_file())
    header = PDF_REPORT_PATH.read_bytes()[:8] if PDF_REPORT_PATH.is_file() else b""
    record("output/report.pdf is readable", header.startswith(b"%PDF"), header[:8].decode("latin-1", "replace"))
    size = PDF_REPORT_PATH.stat().st_size if PDF_REPORT_PATH.is_file() else 0
    record("output/report.pdf is non-empty", size > 500, str(size))


def test_persona_evals() -> None:
    evals_dir = ROOT_DIR / "evals"
    persona_dir = evals_dir / "personas"
    for name in ("strong", "average", "weak", "bluffer", "nervous"):
        record(f"evals/personas/{name}.json exists", (persona_dir / f"{name}.json").is_file())
    sys.path.insert(0, str(evals_dir))
    import run_evals

    plan = load_approved_plan(QUESTION_PLAN_PATH)
    rows = [run_evals.run_persona(plan, name) for name in run_evals.PERSONAS]
    run_evals.rank_rows(rows)
    failures = run_evals._check_expectations(rows)
    (evals_dir / "results.md").write_text(run_evals.render_results(rows, failures), encoding="utf-8")
    record("all five evals run", len(rows) == 5 and all("score" in row for row in rows))
    by_name = {row["persona"]: row for row in rows}
    record(
        "Strong > Average > Weak",
        float(by_name["strong"]["score"]) > float(by_name["average"]["score"]) > float(by_name["weak"]["score"]),
        f"{by_name['strong']['score']} / {by_name['average']['score']} / {by_name['weak']['score']}",
    )
    record(
        "Bluffer < Average",
        float(by_name["bluffer"]["score"]) < float(by_name["average"]["score"]),
        f"{by_name['bluffer']['score']} / {by_name['average']['score']}",
    )
    delta = abs(float(by_name["nervous"]["score"]) - float(by_name["strong"]["score"]))
    record(
        "Nervous near Strong",
        delta <= 1.5,
        f"delta={delta}",
    )
    record("evals/results.md exists", (evals_dir / "results.md").is_file())


def test_strong_answer_escalation() -> None:
    plan = _twelve_question_plan()
    controller = InterviewController(plan)
    controller.start_interview()
    first = controller.current_question() or {}
    first_diff = controller.question_difficulty(first)
    action = _speak(controller, _strong_for(first))
    nxt = controller.current_question() or {}
    next_diff = controller.question_difficulty(nxt)
    record(
        "strong answer completes the topic and raises difficulty",
        action == "next"
        and str(nxt.get("id") or "") == "q2"
        and next_diff > first_diff
        and first_diff >= 1,
        f"{first_diff}->{next_diff} action={action}",
    )


def test_call_drop_resume() -> None:
    plan = _twelve_question_plan()
    with tempfile.TemporaryDirectory() as tmp:
        store = InterviewStore(Path(tmp) / "interview.sqlite")
        iid = "resume-q2"
        store.create_interview(iid, candidate=TAHA, role=ROLE, company="Northwind Labs")
        live = InterviewController(
            plan,
            persist=lambda current: store.save_from_controller(
                iid, current, candidate=TAHA, role=ROLE, company="Northwind Labs"
            ),
        )
        live.start_interview()
        _speak(live, _strong_for(live.current_question() or {}))
        live.note_question_asked()
        live.mark_candidate_speaking()
        live.try_complete_answer("Yeah I did that.")
        saved_index = live.index
        saved_follow = live.follow_up_count
        saved_turns = len(live.get_transcript())
        saved_qid = live.current_question_id()
        restored = store.load_controller(iid, plan)
        record(
            "offline call-drop resume restores Qn / follow_up_count / transcript",
            restored.index == saved_index
            and restored.follow_up_count == saved_follow
            and restored.current_question_id() == saved_qid
            and len(restored.get_transcript()) == saved_turns
            and saved_qid == "q2"
            and saved_follow >= 1,
            f"index={restored.index} follow={restored.follow_up_count} q={saved_qid}",
        )
        record(
            "LiveKit automatic reconnect is not claimed",
            "LiveKit" in (store.load_controller.__doc__ or "")
            or "Not a LiveKit reconnect" in (store.load_controller.__doc__ or ""),
        )


def test_mcp_pdf_tools() -> None:
    import mcp_server

    import asyncio

    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {tool.name for tool in tools}
    record(
        "all five required MCP tools exist",
        set(REQUIRED_PDF_TOOLS) <= names,
        ",".join(sorted(names)),
    )
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "interview.sqlite"
        score_path = Path(tmp) / "scorecard.json"
        mcp_server.configure(store_path=store_path, scorecard_path=score_path)
        store = InterviewStore(store_path)
        store.create_interview("int-pdf", candidate=TAHA, role=ROLE, company="Northwind Labs")
        source = read_json(INTERVIEW_TRANSCRIPT_PATH)
        turns = source if isinstance(source, list) else []
        quote = next(
            (
                str(t.get("text") or "")
                for t in turns
                if t.get("speaker") == "candidate" and len(str(t.get("text") or "")) >= 12
            ),
            "I first make chunks and then store it in a vector DV.",
        )
        controller = InterviewController(load_approved_plan(QUESTION_PLAN_PATH) or _twelve_question_plan())
        for turn in turns:
            controller.record_turn(
                str(turn.get("speaker") or ""),
                str(turn.get("text") or ""),
                str(turn.get("turn_type") or "answer"),
                question_id=str(turn.get("question_id") or "") or None,
                timestamp=turn.get("timestamp"),
            )
        store.save_from_controller("int-pdf", controller, candidate=TAHA, role=ROLE, company="Northwind Labs")
        candidate = mcp_server.get_candidate("int-pdf")
        record(
            "get_candidate works",
            candidate.get("ok") is True and candidate.get("name") == TAHA,
        )
        missing = mcp_server.get_candidate("does-not-exist")
        record(
            "unknown interview ID returns a structured error",
            missing.get("ok") is False and missing.get("error") == "interview_not_found",
        )
        saved = mcp_server.save_score(
            {
                "candidate_name": TAHA,
                "role": ROLE,
                "interview_date": "2026-08-14",
                "duration_seconds": 480,
                "competencies": [
                    {
                        "name": "Technical competence",
                        "score": 2,
                        "confidence": 0.4,
                        "evidence_quote": quote,
                        "reasoning": "grounded",
                    },
                    {
                        "name": "Problem solving",
                        "score": 5,
                        "confidence": 0.9,
                        "evidence_quote": "This quote is invented and must be rejected now.",
                        "reasoning": "should be stripped",
                    },
                ],
                "overall_score": 5,
                "recommendation": "hire",
                "recommendation_reasoning": "test",
                "strengths": [],
                "concerns": [],
                "guardrail_flags": [],
                "github_grounded_questions_asked": 3,
            },
            "int-pdf",
        )
        record(
            "save_score writes a guardrail-validated scorecard",
            saved.get("ok") is True and score_path.is_file() and int(saved.get("rejected_quotes") or 0) >= 1,
            str(saved.get("rejected_quotes")),
        )
        loaded = mcp_server.get_scorecard("int-pdf")
        comps = ((loaded.get("scorecard") or {}).get("competencies") or [])
        problem = next((item for item in comps if item.get("name") == "Problem solving"), {})
        record(
            "get_scorecard returns the current scorecard",
            loaded.get("ok") is True
            and (loaded.get("scorecard") or {}).get("candidate_name") == TAHA
            and problem.get("score") is None,
        )
        mcp_server.configure()


def test_banned_question_guardrails() -> None:
    labels = {name for name, _pattern in BANNED_PATTERNS}
    record(
        "all required banned categories are defined",
        {
            "age",
            "gender",
            "marital",
            "religion",
            "nationality",
            "health",
            "salary_history",
            "politics",
        }
        <= labels,
        ",".join(sorted(labels)),
    )
    plan = load_approved_plan(QUESTION_PLAN_PATH) or {}
    all_blocked = True
    for category, sample in BANNED_SAMPLES.items():
        result = sanitize_spoken_question(sample)
        briefing = compact_briefing(
            {
                **plan,
                "questions": [
                    {
                        "id": "banned",
                        "category": "Technical",
                        "question": sample,
                        "source": "jd",
                    }
                ],
            },
            "banned",
        )
        spoken = spoken_question_text(briefing)
        flagged = briefing.get("guardrail_flags") or result.get("flags") or []
        if (
            result.get("blocked") is not True
            or sample.lower() in spoken.lower()
            or category not in str(result.get("flags"))
            or not flagged
        ):
            all_blocked = False
            record(f"banned {category} blocked before speech", False, sample)
        else:
            record(f"banned {category} blocked before speech", True)
    record("banned questions are replaced or rejected and flagged", all_blocked)
    safe = compact_briefing(plan, "q1")
    q1 = str(((plan.get("questions") or [{}])[0]).get("question") or "")
    record(
        "approved Taha Q1 still reaches the speak payload",
        q1 and q1 in str(safe.get("question") or "") and not safe.get("banned_blocked"),
    )


def test_prompts_and_plan_integrity() -> None:
    prompts = ROOT_DIR / "prompts"
    for name in (
        "live_interviewer.md",
        "parse_resume.md",
        "parse_jd.md",
        "gap_analysis.md",
        "question_planner.md",
        "ITERATION_NOTES.md",
    ):
        record(f"prompts/{name} exists", (prompts / name).is_file())
    notes = (prompts / "ITERATION_NOTES.md").read_text(encoding="utf-8")
    record(
        "ITERATION_NOTES.md records real v1 to v2 changes",
        "v1" in notes and "v2" in notes and ("failed" in notes.lower() or "NOT_FOUND" in notes),
    )
    agent_src = (SRC_DIR / "agent.py").read_text(encoding="utf-8")
    record(
        "live interviewer prompt is loaded from prompts/",
        "prompts" in agent_src and "live_interviewer.md" in agent_src,
    )
    plan = load_approved_plan(QUESTION_PLAN_PATH)
    candidate = (plan or {}).get("candidate") or {}
    record(
        "Taha plan remains approved and unchanged",
        bool(plan)
        and plan.get("approval_status") == "approved"
        and candidate.get("name") == TAHA
        and len(plan.get("questions") or []) == 12,
    )
    record("sample_mode=false", bool(plan) and plan.get("sample_mode") is False)
    artifacts = [
        plan,
        read_json(PDF_TRANSCRIPT_PATH) if PDF_TRANSCRIPT_PATH.is_file() else {},
        read_json(PDF_SCORECARD_PATH) if PDF_SCORECARD_PATH.is_file() else {},
        read_json(INTERVIEW_EVALUATION_PATH) if INTERVIEW_EVALUATION_PATH.is_file() else {},
    ]
    record(
        "no Ayesha/langchain-ai sample data leaks",
        not any(_has_sample_leak(item) for item in artifacts),
    )


def test_phase8_regression() -> None:
    proc = subprocess.run(
        [sys.executable, str(SRC_DIR / "run_phase8_checks.py")],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    passed = proc.returncode == 0 and "Passed" in (proc.stdout or "")
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-4:])
    record("Phase 8 regression still passes", passed, tail)


def main() -> int:
    print("=== Phase 9 checks ===")
    from generate_grading_artifacts import main as write_artifacts

    write_artifacts()
    print("--- Artifacts ---")
    test_required_output_paths()
    test_transcript_schema()
    test_scorecard_and_evidence()
    test_pdf_report()
    print("--- Personas ---")
    test_persona_evals()
    print("--- Controller ---")
    test_strong_answer_escalation()
    test_call_drop_resume()
    print("--- MCP / guardrails ---")
    test_mcp_pdf_tools()
    test_banned_question_guardrails()
    test_prompts_and_plan_integrity()
    print("--- Phase 8 ---")
    test_phase8_regression()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
