"""Offline and live checks for the Phase 2 prep graph."""

from __future__ import annotations

import inspect
import json
import sqlite3
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from langgraph.types import Command

from agents.github_agent import _jd_terms, _rank_repos, analyze_github
from agents.question_planner import REQUIRED_CATEGORIES
from config import CHECKPOINT_PATH, QUESTION_PLAN_PATH, load_prep_settings
from graph import (
    compile_prep_graph,
    route_after_github_extract,
    route_after_review,
    route_after_validation,
)
from nodes.github import extract_github
from nodes.validate import validate_question_plan
from plan_loader import describe_loaded_plan, load_approved_plan
from prep.banned import banned_hits
from prep.github_api import commit_touches_file, parse_github_username, parse_owner_repo
from prep.paths import GITHUB_JSON, JD_JSON, PREP_QUESTION_PLAN, PROFILE_JSON, RESUME_JSON
from prep.pdf import extract_text, find_github_urls
from prep.question_quality import ALLOWED_SOURCES, semantic_issue
from prep.samples import SAMPLE_WARNING, write_sample_inputs

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{': ' + detail if detail else ''}")


def test_offline() -> None:
    resume_path, jd_path = write_sample_inputs()
    text, extractor = extract_text(resume_path)
    record("Resume PDF parsed", "Ayesha Malik" in text and "LangChain" in text, extractor)
    jd_text, jd_extractor = extract_text(jd_path)
    record("JD parsed", "Junior AI Engineer" in jd_text and "RAG" in jd_text, jd_extractor)
    urls = find_github_urls(text)
    record("GitHub URL extracted", any("langchain-ai" in url for url in urls), ",".join(urls))
    record(
        "GitHub username parse",
        parse_github_username("https://github.com/langchain-ai") == "langchain-ai",
    )
    record(
        "Banned question filter",
        "age" in banned_hits("How old are you?")
        and not banned_hits("How did you debug the RAG pipeline?"),
    )

    bad_state = {
        "questions": [{"id": "q1", "category": "Technical", "question": "Hi", "source_reference": ""}],
        "generation_attempt": 1,
        "github": {"projects": [{"name": "x"}], "error": ""},
    }
    validation = validate_question_plan(bad_state)["validation"]
    record(
        "Question validation works",
        validation["ok"] is False and validation["issues"],
        str(len(validation["issues"])) + " issues",
    )
    record(
        "Conditional edge: validation retry",
        route_after_validation({"validation": {"ok": False}, "generation_attempt": 1})
        == "generate_question_plan",
    )
    record(
        "Conditional edge: validation pass",
        route_after_validation({"validation": {"ok": True}, "generation_attempt": 1})
        == "recruiter_review",
    )
    record(
        "Conditional edge: reject regenerates",
        route_after_review({"recruiter_action": "reject"}) == "generate_question_plan",
    )
    record(
        "Conditional edge: approve finalizes",
        route_after_review({"recruiter_action": "approve", "validation": {"ok": True}})
        == "finalize_plan",
    )
    record(
        "Conditional edge: edit revalidates",
        route_after_review({"recruiter_action": "edit"}) == "validate_question_plan",
    )
    record(
        "Conditional edge: unknown action stays in HITL",
        route_after_review({"recruiter_action": "invalid"}) == "recruiter_review",
    )
    record(
        "Conditional edge: valid edit finalizes",
        route_after_validation({"validation": {"ok": True}, "approval_status": "edited"})
        == "finalize_plan",
    )
    record(
        "Conditional edge: invalid edit cannot finalize",
        route_after_validation({"validation": {"ok": False}, "approval_status": "edited"})
        == "recruiter_review",
    )
    record(
        "Conditional edge: missing GitHub skips analyze",
        route_after_github_extract({"github_username": "", "github_error": "missing"})
        == "generate_question_plan",
    )

    source = inspect.getsource(_jd_terms)
    record(
        "JD ranking does not use hardcoded AI terms",
        all(term not in source for term in ('"langchain"', '"langgraph"', '"fastapi"', '"llm"', '"agent"')),
    )
    frontend_jd = {
        "role": "Frontend Engineer",
        "required_skills": ["React", "TypeScript", "CSS"],
        "preferred_skills": ["Next.js"],
        "technologies": ["React", "Next.js"],
        "responsibilities": ["Build responsive UI"],
        "domain_knowledge": ["accessibility"],
        "competencies": ["frontend fundamentals"],
    }
    terms = _jd_terms(frontend_jd)
    record("Frontend JD terms exclude LangChain", "langchain" not in terms and "react" in terms)
    ranked = _rank_repos(
        [
            {
                "name": "shop-ui",
                "description": "React Next.js storefront",
                "language": "TypeScript",
                "topics": ["react"],
                "stargazers_count": 2,
                "fork": False,
                "owner": {"login": "candidate"},
            },
            {
                "name": "langchain",
                "description": "The agent engineering platform",
                "language": "Python",
                "topics": ["llm"],
                "stargazers_count": 140000,
                "fork": False,
                "owner": {"login": "candidate"},
            },
        ],
        frontend_jd,
    )
    record("Frontend JD ranks React repo above LangChain", ranked[0]["name"] == "shop-ui", ranked[0]["name"])

    extracted = extract_github(
        {
            "github_url_override": "https://github.com/octocat",
            "github_url": "https://github.com/langchain-ai",
        }
    )
    record(
        "Real candidate GitHub override wins over sample",
        extracted.get("github_username") == "octocat" and not extracted.get("sample_mode"),
        extracted.get("github_username", ""),
    )


def _category_ok(questions: list[dict]) -> bool:
    counts = Counter(q.get("category") for q in questions)
    return all(counts.get(name, 0) == expected for name, expected in REQUIRED_CATEGORIES)


def _sources_ok(questions: list[dict]) -> bool:
    return all(str(q.get("source") or "") in ALLOWED_SOURCES for q in questions)


def _semantics_ok(questions: list[dict]) -> bool:
    return not any(semantic_issue(q) for q in questions)


def _file_commit_ok(questions: list[dict]) -> tuple[bool, str]:
    checked = 0
    for question in questions:
        if str(question.get("source") or "") != "github":
            continue
        sha = str(question.get("commit") or "")
        path = str(question.get("file") or "")
        if not sha:
            continue
        owner, repo = parse_owner_repo(str(question.get("repository") or ""))
        if not commit_touches_file(owner, repo, path, sha):
            return False, f"{question.get('id')} {path}@{sha[:7]}"
        checked += 1
    return checked > 0, f"verified={checked}"


def test_live_pipeline() -> None:
    load_prep_settings()
    resume_path, jd_path = write_sample_inputs()
    graph, conn = compile_prep_graph()
    try:
        thread_id = "phase2-live-check-" + str(int(time.time()))
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(
            {
                "thread_id": thread_id,
                "resume_path": str(resume_path),
                "jd_path": str(jd_path),
                "github_url_override": "https://github.com/langchain-ai",
            },
            config,
        )
        interrupted = bool(result.get("__interrupt__") or graph.get_state(config).next)
        record("HITL interrupts graph", interrupted, str(graph.get_state(config).next))
        record(
            "SQLite checkpoint created",
            CHECKPOINT_PATH.is_file() and CHECKPOINT_PATH.stat().st_size > 0,
            str(CHECKPOINT_PATH),
        )
        with sqlite3.connect(CHECKPOINT_PATH) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        record("SQLite has checkpoint tables", any("checkpoint" in name for name in tables), ",".join(tables[:6]))

        values = graph.get_state(config).values or {}
        record(
            "Candidate profile created",
            bool((values.get("candidate_profile") or {}).get("name")),
            str((values.get("candidate_profile") or {}).get("name")),
        )
        record(
            "Gap analysis generated",
            bool(
                (values.get("gap_analysis") or {}).get("matched_skills")
                or (values.get("gap_analysis") or {}).get("missing_skills")
            ),
        )
        github = values.get("github") or {}
        record(
            "GitHub repositories retrieved",
            int(github.get("repos_considered") or 0) > 0,
            str(github.get("repos_considered")),
        )
        projects = github.get("projects") or []
        record(
            "Top 3 relevant projects selected",
            len(projects) == 3,
            ",".join(p.get("name", "") for p in projects),
        )
        record(
            "GitHub evidence references generated",
            all(p.get("url") and (p.get("file_path") or p.get("readme_path")) for p in projects),
        )
        record(
            "Sample mode warning present",
            bool(github.get("sample_mode") and github.get("warning") == SAMPLE_WARNING),
        )
        questions = values.get("questions") or []
        before_reject = [str(q.get("question") or "") for q in questions]
        record("Exactly 12 questions generated", len(questions) == 12, str(len(questions)))
        record("Correct category distribution", _category_ok(questions))
        record("Source enum is jd|resume|github|scenario", _sources_ok(questions), ",".join(sorted({str(q.get("source")) for q in questions})))
        record("Question categories match semantic intent", _semantics_ok(questions))
        ok_commit, commit_detail = _file_commit_ok(questions)
        record("GitHub file@commit relationship is valid", ok_commit, commit_detail)

        unknown = graph.invoke(Command(resume={"action": "please_approve"}), config)
        record(
            "Unknown HITL action cannot approve",
            not unknown.get("finalized") and bool(graph.get_state(config).next),
            str(graph.get_state(config).next),
        )

        graph.invoke(Command(resume={"action": "reject", "reason": "regenerate for test"}), config)
        after_values = graph.get_state(config).values or {}
        after_reject = [str(q.get("question") or "") for q in (after_values.get("questions") or [])]
        record(
            "Reject regenerates question content",
            before_reject != after_reject and int(after_values.get("generation_attempt") or 0) >= 2,
            f"attempt={after_values.get('generation_attempt')} changed={before_reject != after_reject}",
        )
        record("Resume after interrupt works", bool(graph.get_state(config).next))

        invalid_edit = graph.invoke(
            Command(resume={"action": "edit", "edits": [{"id": "q1", "question": "How old are you?"}]}),
            config,
        )
        record(
            "Invalid edited question cannot finalize",
            not invalid_edit.get("finalized") and bool(graph.get_state(config).next),
            str((graph.get_state(config).values or {}).get("validation", {}).get("issues", [])[:2]),
        )

        edited_text = "Walk me through how you would evaluate retrieval quality after a bad production answer."
        edit_result = graph.invoke(
            Command(resume={"action": "edit", "edits": [{"id": "q1", "question": edited_text}]}),
            config,
        )
        record(
            "Editing a question triggers validation",
            bool(edit_result.get("finalized") or graph.get_state(config).next),
        )
        record(
            "Recruiter can edit",
            bool(edit_result.get("finalized"))
            and any(q.get("question") == edited_text for q in (edit_result.get("questions") or [])),
            edit_result.get("approval_status", ""),
        )

        approve_thread = "phase2-approve-check-" + str(int(time.time()))
        approve_config = {"configurable": {"thread_id": approve_thread}}
        graph.invoke(
            {
                "thread_id": approve_thread,
                "resume_path": str(resume_path),
                "jd_path": str(jd_path),
                "github_url_override": "https://github.com/langchain-ai",
            },
            approve_config,
        )
        approved = graph.invoke(Command(resume={"action": "approve"}), approve_config)
        record(
            "Recruiter can approve",
            bool(approved.get("finalized")) and approved.get("approval_status") == "approved",
        )
        record(
            "Final approved plan saved",
            QUESTION_PLAN_PATH.is_file() and PREP_QUESTION_PLAN.is_file(),
            str(QUESTION_PLAN_PATH),
        )
        plan = load_approved_plan()
        record("plan_loader reads approved plan", plan is not None, describe_loaded_plan())
        if plan:
            plan_questions = plan.get("questions") or []
            record("Saved plan has 12 questions", len(plan_questions) == 12)
            record("Saved plan source enum valid", _sources_ok(plan_questions))
            record("Saved plan semantics valid", _semantics_ok(plan_questions))
            ok_saved, saved_detail = _file_commit_ok(plan_questions)
            record("Saved plan GitHub file@commit valid", ok_saved, saved_detail)
            record(
                "Saved plan has no banned questions",
                not any(banned_hits(str(q.get("question") or "")) for q in plan_questions),
            )
            record("Saved plan approval status correct", plan.get("approval_status") == "approved")
        record("output/prep/resume.json exists", RESUME_JSON.is_file())
        record("output/prep/jd.json exists", JD_JSON.is_file())
        record("output/prep/github.json exists", GITHUB_JSON.is_file())
        record("output/prep/candidate_profile.json exists", PROFILE_JSON.is_file())

        previous_github = GITHUB_JSON.read_text(encoding="utf-8") if GITHUB_JSON.is_file() else ""
        other = analyze_github(
            "https://github.com/octocat",
            {
                "role": "Software Engineer",
                "required_skills": ["git"],
                "technologies": ["git"],
                "preferred_skills": [],
                "responsibilities": ["Ship small tools"],
                "domain_knowledge": [],
                "competencies": [],
            },
        )
        other_projects = other.get("projects") or []
        record(
            "Real candidate GitHub URL mode works",
            other.get("username") == "octocat"
            and not other.get("sample_mode")
            and bool(other_projects)
            and all("github.com/octocat/" in str(p.get("url") or "") for p in other_projects),
            ",".join(p.get("name", "") for p in other_projects),
        )
        if previous_github:
            GITHUB_JSON.write_text(previous_github, encoding="utf-8")
    finally:
        conn.close()


def test_phase1_not_broken() -> None:
    from agent import AGENT_NAME, GEMINI_LIVE_MODEL, INTERVIEWER_INSTRUCTIONS, _realtime_model

    record("Phase 1 agent name unchanged", AGENT_NAME == "firstround-interviewer")
    record("Phase 1 Gemini Live model unchanged", GEMINI_LIVE_MODEL.endswith("native-audio-preview-12-2025"))
    record("Phase 1 interviewer instructions still present", "AI interviewer" in INTERVIEWER_INSTRUCTIONS)
    model = _realtime_model()
    record("Phase 1 RealtimeModel still constructs", model is not None, type(model).__name__)


def main() -> int:
    print("=== Phase 2 checks ===")
    try:
        test_offline()
    except Exception as exc:
        record("Offline checks", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    try:
        test_live_pipeline()
    except Exception as exc:
        record("Live pipeline", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    try:
        test_phase1_not_broken()
    except Exception as exc:
        record("Existing Phase 1 still works", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    else:
        record("Existing Phase 1 still works", True)

    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    Path("output/prep/phase2_check_results.json").write_text(
        json.dumps({"passed": passed, "total": len(RESULTS), "failed": failed, "results": RESULTS}, indent=2),
        encoding="utf-8",
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
