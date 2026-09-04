"""Offline Phase 8 checks: full demo artifact chain. Does not start LiveKit."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    GEMINI_LIVE_MODEL,
    INTERVIEW_EVALUATION_PATH,
    INTERVIEW_REPORT_JSON_PATH,
    INTERVIEW_REPORT_MD_PATH,
    INTERVIEW_STORE_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    QUESTION_PLAN_PATH,
)
from plan_loader import is_ready_for_live_interview, load_approved_plan
from prep.io import read_json
from prep.paths import GAP_JSON, PROFILE_JSON
from realtime.evaluate_interview import (
    GO_MIN_FIT,
    GO_MIN_GITHUB,
    GO_MIN_OVERALL,
    GO_MIN_TECH,
    evaluate_interview,
)
from realtime.report import generate_report
from realtime.store import InterviewStore
from run_phase3_slice1_checks import RESULTS, record, test_phase1_realtime_unchanged
from run_phase3_slice2_checks import (
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
from run_phase3_slice5_checks import test_report_generator, test_real_taha_report, test_slice5_hooks
from run_phase3_slice55_checks import (
    test_behavioral_and_speakability,
    test_github_grounding,
    test_plan_rules,
    test_slice55_hooks,
)
from run_phase6_checks import (
    test_completion_and_timer,
    test_disconnect_and_duplicates,
    test_phase6_hooks,
    test_report_from_store,
    test_sqlite_store,
)
from run_phase7_checks import (
    _file_digest,
    _seed_interview,
    test_mcp_server_and_tools,
    test_phase7_hooks,
)

TAHA = "Muhammad Taha Farrukh"
ROLE = "Junior AI Engineer"
COMPANY = "Northwind Labs"
GITHUB = "https://github.com/MTahaFarrukh"


def _load_optional(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


def _has_sample_leak(payload: object) -> bool:
    text = json.dumps(payload, ensure_ascii=False).lower() if not isinstance(payload, str) else payload.lower()
    if "ayesha" in text:
        return True
    return "github.com/langchain-ai" in text


def test_phase8_artifact_chain() -> None:
    plan = load_approved_plan(QUESTION_PLAN_PATH)
    candidate = (plan or {}).get("candidate") or {}
    job = (plan or {}).get("job") or {}
    questions = (plan or {}).get("questions") or []
    record(
        "approved plan exists and is Taha's real plan",
        bool(plan)
        and is_ready_for_live_interview(plan)
        and candidate.get("name") == TAHA
        and job.get("role") == ROLE
        and job.get("company") == COMPANY
        and str(candidate.get("github_url") or "") == GITHUB,
    )
    record("sample_mode=false", bool(plan) and plan.get("sample_mode") is False)
    record("12 questions exist", isinstance(questions, list) and len(questions) == 12)

    transcript = read_json(INTERVIEW_TRANSCRIPT_PATH) if INTERVIEW_TRANSCRIPT_PATH.is_file() else []
    record(
        "on-disk transcript exists",
        isinstance(transcript, list) and len(transcript) >= 2,
    )
    evaluation = evaluate_interview(
        plan or {},
        transcript if isinstance(transcript, list) else [],
        profile=_load_optional(PROFILE_JSON),
        gap=_load_optional(GAP_JSON) or (plan or {}).get("gap_analysis"),
    )
    record(
        "transcript can be evaluated",
        evaluation.get("recommendation") in {"GO", "NO_GO", "REVIEW"}
        and (evaluation.get("candidate") or {}).get("name") == TAHA
        and (evaluation.get("candidate") or {}).get("role") == ROLE,
    )
    report = generate_report(plan or {}, transcript, evaluation)
    record(
        "evaluation can generate the report",
        (report.get("decision") or {}).get("recommendation") == evaluation.get("recommendation")
        and report.get("interview_status") in {"partial", "completed"}
        and (report.get("candidate") or {}).get("name") == TAHA,
    )

    disk_eval = _load_optional(INTERVIEW_EVALUATION_PATH) or {}
    disk_report = _load_optional(INTERVIEW_REPORT_JSON_PATH) or {}
    record(
        "report and evaluation candidate/role match the approved plan",
        (disk_eval.get("candidate") or {}).get("name") == TAHA
        and (disk_eval.get("candidate") or {}).get("role") == ROLE
        and (disk_eval.get("candidate") or {}).get("company") == COMPANY
        and (disk_report.get("candidate") or {}).get("name") == TAHA
        and (disk_report.get("candidate") or {}).get("role") == ROLE
        and (disk_report.get("candidate") or {}).get("company") == COMPANY
        and (evaluation.get("candidate") or {}).get("company") == COMPANY
        and (report.get("candidate") or {}).get("role") == ROLE,
    )

    final_artifacts = [
        {"candidate": candidate, "job": job, "sample_mode": (plan or {}).get("sample_mode")},
        transcript,
        disk_eval,
        disk_report,
        INTERVIEW_REPORT_MD_PATH.read_text(encoding="utf-8") if INTERVIEW_REPORT_MD_PATH.is_file() else "",
    ]
    record(
        "no Ayesha/langchain-ai sample data leaks into the final artifacts",
        not any(_has_sample_leak(item) for item in final_artifacts),
    )

    plan_before = _file_digest(QUESTION_PLAN_PATH)
    eval_before = _file_digest(INTERVIEW_EVALUATION_PATH)
    report_before = _file_digest(INTERVIEW_REPORT_JSON_PATH)
    live_before = _file_digest(INTERVIEW_STORE_PATH)

    import mcp_server

    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "interview.sqlite"
        mcp_server.configure(store_path=store_path)
        store = InterviewStore(store_path)
        _seed_interview(store, "demo-taha")
        loaded = store.get_interview("demo-taha")
        record(
            "SQLite interview store can load an interview",
            loaded is not None
            and loaded.get("interview_id") == "demo-taha"
            and loaded.get("candidate") == TAHA
            and isinstance(store.get_transcript("demo-taha"), list)
            and len(store.get_transcript("demo-taha")) >= 2,
        )
        sqlite_before = _file_digest(store_path)

        status = mcp_server.get_interview_status("demo-taha")
        mcp_transcript = mcp_server.get_interview_transcript("demo-taha")
        mcp_report = mcp_server.get_interview_report("demo-taha")
        record(
            "MCP can read interview status/transcript/report",
            status.get("ok") is True
            and status.get("candidate") == TAHA
            and mcp_transcript.get("ok") is True
            and len(mcp_transcript.get("turns") or []) >= 2
            and mcp_report.get("ok") is True
            and mcp_report.get("available") is True
            and (mcp_report.get("candidate") or {}).get("name") == TAHA
            and mcp_report.get("recommendation") in {"GO", "NO_GO", "REVIEW"},
        )
        record(
            "no MCP operation mutates the plan/store",
            _file_digest(QUESTION_PLAN_PATH) == plan_before
            and _file_digest(store_path) == sqlite_before
            and not _has_sample_leak([status, mcp_transcript, mcp_report]),
        )
        mcp_server.configure()

    record(
        "production artifacts were not overwritten by Phase 8 checks",
        _file_digest(QUESTION_PLAN_PATH) == plan_before
        and _file_digest(INTERVIEW_EVALUATION_PATH) == eval_before
        and _file_digest(INTERVIEW_REPORT_JSON_PATH) == report_before
        and _file_digest(INTERVIEW_STORE_PATH) == live_before,
    )


def test_phase8_hooks() -> None:
    import inspect
    import agent
    import mcp_server

    model_src = inspect.getsource(agent._realtime_model)
    session_src = inspect.getsource(agent.interview_session)
    record(
        "Gemini Live model id unchanged",
        GEMINI_LIVE_MODEL == "gemini-2.5-flash-native-audio-preview-12-2025"
        and "model=GEMINI_LIVE_MODEL" in model_src,
    )
    record(
        "LiveKit audio path still excludes MCP",
        "mcp_server" not in session_src
        and "room_io.AudioInputOptions()" in session_src
        and 'voice="Puck"' in model_src,
    )
    record(
        "evaluator thresholds unchanged",
        GO_MIN_OVERALL == 70 and GO_MIN_FIT == 60 and GO_MIN_TECH == 60 and GO_MIN_GITHUB == 50,
    )
    record(
        "MCP remains stdio and read-only",
        mcp_server.mcp.name == "firstround"
        and "save_from_controller" not in Path(inspect.getsourcefile(mcp_server)).read_text(encoding="utf-8"),
    )


def main() -> int:
    print("=== Phase 8 checks ===")
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
    print("--- Phase 7 ---")
    test_mcp_server_and_tools()
    print("--- Phase 8 ---")
    test_phase8_artifact_chain()
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    test_slice4_hooks()
    test_slice5_hooks()
    test_slice55_hooks()
    test_phase6_hooks()
    test_phase7_hooks()
    test_phase8_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
