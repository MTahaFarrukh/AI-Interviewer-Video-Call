"""Offline checks for Phase 7: read-only recruiter MCP (FastMCP stdio)."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import tempfile
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    INTERVIEW_EVALUATION_PATH,
    INTERVIEW_REPORT_JSON_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    QUESTION_PLAN_PATH,
)
from fastmcp import Client, FastMCP
from prep.io import read_json
from realtime.controller import InterviewController
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


def _file_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_interview(store: InterviewStore, interview_id: str, *, status: str = "partial") -> InterviewController:
    plan = read_json(QUESTION_PLAN_PATH)
    store.create_interview(
        interview_id,
        candidate="Muhammad Taha Farrukh",
        role="Junior AI Engineer",
        company="Northwind Labs",
    )
    controller = InterviewController(
        plan,
        persist=lambda current: store.save_from_controller(
            interview_id,
            current,
            status=status,
            candidate="Muhammad Taha Farrukh",
            role="Junior AI Engineer",
            company="Northwind Labs",
        ),
    )
    controller.start_interview()
    transcript = read_json(INTERVIEW_TRANSCRIPT_PATH)
    if not isinstance(transcript, list):
        transcript = []
    for turn in transcript:
        if not isinstance(turn, dict):
            continue
        controller.record_turn(
            str(turn.get("speaker") or ""),
            str(turn.get("text") or ""),
            str(turn.get("turn_type") or "answer"),
            question_id=str(turn.get("question_id") or "") or None,
            timestamp=turn.get("timestamp"),
        )
    store.save_from_controller(
        interview_id,
        controller,
        status=status,
        candidate="Muhammad Taha Farrukh",
        role="Junior AI Engineer",
        company="Northwind Labs",
    )
    return controller


def test_mcp_server_and_tools() -> None:
    import mcp_server

    record("MCP server imports successfully", mcp_server.mcp is not None)
    record("FastMCP server is constructed", isinstance(mcp_server.mcp, FastMCP))

    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {tool.name for tool in tools}
    record(
        "All 7 tools are registered",
        set(mcp_server.TOOL_NAMES) <= names,
        detail=",".join(sorted(names)),
    )

    plan_before = _file_digest(QUESTION_PLAN_PATH)
    eval_before = _file_digest(INTERVIEW_EVALUATION_PATH)
    report_before = _file_digest(INTERVIEW_REPORT_JSON_PATH)

    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "interview.sqlite"
        mcp_server.configure(store_path=store_path)
        store = InterviewStore(store_path)
        _seed_interview(store, "int-taha")
        store.create_interview(
            "int-empty",
            candidate="Muhammad Taha Farrukh",
            role="Junior AI Engineer",
            company="Northwind Labs",
        )
        sqlite_before = _file_digest(store_path)

        listed = mcp_server.list_interviews(limit=20)
        record(
            "list_interviews works against a temporary SQLite database",
            listed.get("ok") is True
            and listed.get("count", 0) >= 2
            and listed["interviews"][0]["interview_id"] in {"int-taha", "int-empty"},
        )

        status = mcp_server.get_interview_status("int-taha")
        record(
            "get_interview_status works",
            status.get("ok") is True
            and status.get("interview_id") == "int-taha"
            and status.get("candidate") == "Muhammad Taha Farrukh"
            and status.get("status") == "partial"
            and "transcript" not in status,
        )

        transcript = mcp_server.get_interview_transcript("int-taha")
        turns = transcript.get("turns") or []
        record(
            "get_interview_transcript works",
            transcript.get("ok") is True
            and len(turns) >= 2
            and {"speaker", "question_id", "turn_type", "text", "timestamp"} <= set(turns[0])
            and all("audio" not in turn for turn in turns),
        )

        current = mcp_server.get_current_question("int-taha")
        approved = read_json(QUESTION_PLAN_PATH)
        q1 = (approved.get("questions") or [{}])[0]
        record(
            "get_current_question reads the approved plan",
            current.get("ok") is True
            and current.get("question_id") == "q1"
            and current.get("question") == q1.get("question")
            and "q8" not in json.dumps(current),
        )

        summary = mcp_server.get_question_plan()
        dumped = json.dumps(summary)
        record(
            "get_question_plan reads the approved plan",
            summary.get("ok") is True
            and summary.get("candidate", {}).get("name") == "Muhammad Taha Farrukh"
            and summary.get("role") == "Junior AI Engineer"
            and summary.get("company") == "Northwind Labs"
            and summary.get("sample_mode") is False
            and summary.get("approval_status") == "approved"
            and summary.get("question_ids") == [f"q{i}" for i in range(1, 13)]
            and "muhammadtahafarrukh@gmail.com" not in dumped.lower()
            and "Volunteer, NED Techfest" not in dumped
            and "Ayesha" not in dumped
            and "langchain-ai" not in dumped.lower(),
        )

        github = mcp_server.get_github_evidence("q8")
        record(
            "get_github_evidence returns the correct repo/file/SHA",
            github.get("ok") is True
            and "Conditional-RAG-Uni-Chatbot" in str(github.get("repository") or "")
            and github.get("file") == "conditional_RAG.py"
            and str(github.get("commit") or "").startswith("7dcc77e")
            and "conditional_RAG.py@7dcc77e" in str(github.get("source_reference") or ""),
        )

        report = mcp_server.get_interview_report("int-taha")
        record(
            "get_interview_report works against the existing real Taha interview data or a deterministic fixture",
            report.get("ok") is True
            and report.get("available") is True
            and (report.get("candidate") or {}).get("name") == "Muhammad Taha Farrukh"
            and report.get("recommendation") in {"GO", "NO_GO", "REVIEW"}
            and report.get("interview_status") == "partial"
            and report.get("sample_mode") is False,
        )

        missing = mcp_server.get_interview_status("does-not-exist")
        record(
            "Missing interview ID returns a clean error",
            missing.get("ok") is False
            and missing.get("error") == "interview_not_found"
            and "interview_id" in missing,
        )

        bad_q = mcp_server.get_github_evidence("q99")
        record(
            "Invalid question ID returns a clean error",
            bad_q.get("ok") is False
            and bad_q.get("error") == "question_not_found"
            and bad_q.get("question_id") == "q99",
        )

        unavailable = mcp_server.get_interview_report("int-empty")
        record(
            "empty interview returns report not available",
            unavailable.get("ok") is False
            and unavailable.get("error") == "report_not_available",
        )

        os.environ["FIRSTROUND_MCP_FAKE_SECRET"] = "supersecret-mcp-token-value"
        blob = json.dumps(
            [
                listed,
                status,
                transcript,
                current,
                summary,
                github,
                report,
                missing,
                bad_q,
            ]
        )
        env_leak = False
        for name in ("GOOGLE_API_KEY", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GITHUB_TOKEN"):
            value = os.getenv(name, "").strip()
            if len(value) >= 8 and value in blob:
                env_leak = True
        record(
            "No API key/environment secret is returned by any tool",
            not env_leak
            and "supersecret-mcp-token-value" not in blob
            and "LIVEKIT_API_SECRET" not in blob,
        )

        record(
            "MCP cannot mutate the approved question plan",
            _file_digest(QUESTION_PLAN_PATH) == plan_before,
        )
        record(
            "MCP cannot mutate SQLite interview state",
            _file_digest(store_path) == sqlite_before,
        )

        async def _in_process_client() -> list[str]:
            async with Client(mcp_server.mcp) as client:
                client_tools = await client.list_tools()
                plan_result = await client.call_tool("get_question_plan", {})
                data = plan_result.data or {}
                assert data.get("ok") is True
                return [tool.name for tool in client_tools]

        launched = asyncio.run(_in_process_client())
        record(
            "FastMCP in-process client can list tools",
            set(mcp_server.TOOL_NAMES) <= set(launched),
        )

        mcp_server.configure()

    record(
        "offline report files were not overwritten by MCP",
        _file_digest(INTERVIEW_EVALUATION_PATH) == eval_before
        and _file_digest(INTERVIEW_REPORT_JSON_PATH) == report_before,
    )


def test_phase7_hooks() -> None:
    import agent
    import mcp_server
    import realtime.evaluate_interview as evaluator

    mcp_src = Path(inspect.getsourcefile(mcp_server)).read_text(encoding="utf-8")
    agent_src = inspect.getsource(agent.interview_session)
    flow_src = inspect.getsource(agent._attach_linear_flow)
    eval_src = inspect.getsource(evaluator.evaluate_interview)
    frontend_dir = ROOT_DIR / "frontend"
    frontend_names = sorted(p.name for p in frontend_dir.iterdir() if p.is_file())
    record(
        "MCP is not imported on the realtime audio path",
        "mcp_server" not in agent_src
        and "mcp_server" not in flow_src
        and "from mcp_server" not in inspect.getsource(agent),
    )
    record(
        "MCP tools are read-only",
        "save_from_controller" not in mcp_src
        and "mark_status" not in mcp_src
        and "create_interview" not in mcp_src
        and "write_json" not in mcp_src
        and "QUESTION_PLAN_PATH.write" not in mcp_src
        and "subprocess" not in mcp_src,
    )
    record(
        "MCP does not call LiveKit, Gemini, or GitHub APIs",
        "from livekit" not in mcp_src
        and "google.genai" not in mcp_src
        and "RealtimeModel" not in mcp_src
        and "requests." not in mcp_src
        and "urllib.request" not in mcp_src
        and "subprocess" not in mcp_src,
    )
    record(
        "evaluator scoring body unchanged",
        '0.20 * dimensions["jd_resume_fit"]' in eval_src,
    )
    record(
        "frontend unchanged",
        frontend_names == ["app.js", "index.html", "styles.css"],
    )
    record(
        "stdio is the MCP transport",
        "mcp.run()" in mcp_src and 'transport="http"' not in mcp_src,
    )


def main() -> int:
    print("=== Phase 7 checks ===")
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
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    test_slice4_hooks()
    test_slice5_hooks()
    test_slice55_hooks()
    test_phase6_hooks()
    test_phase7_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
