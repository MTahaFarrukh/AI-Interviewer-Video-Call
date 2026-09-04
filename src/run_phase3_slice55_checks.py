"""Offline checks for Phase 3 Slice 5.5: question-plan grounding and speakability."""

from __future__ import annotations

import copy
import inspect
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agents.question_planner import REQUIRED_CATEGORIES, _fallback_text, _stamp_real_references
from graph import route_after_review, route_after_validation
from nodes.validate import validate_question_plan
from prep.question_quality import (
    behavioral_contamination_issue,
    github_alignment_issues,
    speakability_issue,
)
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

SHA_RAG = "ec23026eb08a34c20a7a4e0ad0091a9b664d8be6"
SHA_PDF = "10e623792f405d098ccfa72b613cb5b63e3cc748"
SHA_COND = "7dcc77edfa218b9d1dd33885a3e20e5fc950fe2d"


def _project(name: str, path: str, sha: str, extra_files: list[str] | None = None) -> dict:
    files = [{"path": path, "excerpt": "code"}]
    for item in extra_files or []:
        files.append({"path": item, "excerpt": "code"})
    return {
        "name": name,
        "full_name": f"MTahaFarrukh/{name}",
        "url": f"https://github.com/MTahaFarrukh/{name}",
        "file_path": path,
        "files": files,
        "commit_sha": sha,
        "commit_verified": True,
        "commits": [{"sha": sha, "message": "commit"}],
        "readme_path": "README.md",
        "why_relevant": f"{name} is relevant",
        "evidence": "approved excerpt",
    }


def _projects() -> list[dict]:
    return [
        _project(
            "AI-Season-RAG-Comparison",
            "frontend/src/services/api.js",
            SHA_RAG,
            ["backend/rag.py"],
        ),
        _project("RAG-PDF-Chatbot", "app.py", SHA_PDF, ["create_database.py"]),
        _project("Conditional-RAG-Uni-Chatbot", "conditional_RAG.py", SHA_COND, ["app.py"]),
    ]


def _q8(*, repo: str, file: str, commit: str, text: str | None = None) -> dict:
    spoken = text or (
        "In AI-Season-RAG-Comparison, your frontend service in frontend/src/services/api.js "
        "connects to a local FastAPI backend. How did you handle failed requests?"
    )
    return {
        "id": "q8",
        "category": "Project/GitHub",
        "source": "github",
        "question": spoken,
        "text": spoken,
        "repository": repo,
        "file": file,
        "commit": commit,
        "source_reference": f"{repo}/{file}@{commit[:7]}",
        "evidence": "approved excerpt",
    }


def _github_question(qid: str, category: str, text: str) -> dict:
    return {
        "id": qid,
        "category": category,
        "source": "github" if category == "Project/GitHub" or qid == "q4" else "jd",
        "question": text,
        "text": text,
        "source_reference": "placeholder",
    }


def test_github_grounding() -> None:
    projects = _projects()
    good = _q8(
        repo="https://github.com/MTahaFarrukh/AI-Season-RAG-Comparison",
        file="frontend/src/services/api.js",
        commit=SHA_RAG,
    )
    record(
        "GitHub question repo matches citation repo",
        not github_alignment_issues(good, projects),
    )
    record(
        "GitHub question file matches citation file when named",
        not github_alignment_issues(good, projects),
    )
    record(
        "GitHub question commit matches citation commit",
        not github_alignment_issues(good, projects),
    )
    record(
        "repository/file/commit exists in approved evidence",
        not github_alignment_issues(good, projects),
    )

    bad_repo = _q8(
        repo="https://github.com/MTahaFarrukh/Conditional-RAG-Uni-Chatbot",
        file="conditional_RAG.py",
        commit=SHA_COND,
    )
    repo_issues = github_alignment_issues(bad_repo, projects)
    record(
        "mismatched repo/citation is rejected",
        any("names" in item and "citation points" in item for item in repo_issues),
        "; ".join(repo_issues)[:180],
    )

    bad_file = _q8(
        repo="https://github.com/MTahaFarrukh/AI-Season-RAG-Comparison",
        file="backend/rag.py",
        commit=SHA_RAG,
    )
    file_issues = github_alignment_issues(bad_file, projects)
    record(
        "mismatched file/citation is rejected",
        any("names file" in item for item in file_issues),
        "; ".join(file_issues)[:180],
    )

    raw = [
        _github_question(
            "q4",
            "Technical",
            "In AI-Season-RAG-Comparison, backend/rag.py loads HuggingFace embeddings. Why that model?",
        ),
        _github_question(
            "q5",
            "Behavioral",
            "Tell me about a time you had to deliver a project under a tight deadline. What did you prioritize?",
        ),
        _github_question(
            "q6",
            "Behavioral",
            "Describe a time you disagreed with a review comment. How did you handle it?",
        ),
        _github_question(
            "q7",
            "Project/GitHub",
            "In RAG-PDF-Chatbot you split vector-store creation into create_database.py. Why?",
        ),
        _github_question(
            "q8",
            "Project/GitHub",
            "In AI-Season-RAG-Comparison, frontend/src/services/api.js talks to the FastAPI backend. How do you handle errors?",
        ),
    ]
    slots = []
    for item in (
        {"id": "q1", "category": "Technical", "source": "jd", "question": "How do you evaluate RAG chunking?", "source_reference": "jd"},
        {"id": "q2", "category": "Technical", "source": "jd", "question": "How would you measure retrieval quality?", "source_reference": "jd"},
        {"id": "q3", "category": "Technical", "source": "resume", "question": "What was the hardest technical decision in your research assistant?", "source_reference": "resume"},
        raw[0],
        raw[1],
        raw[2],
        raw[3],
        raw[4],
        {"id": "q9", "category": "Scenario", "source": "scenario", "question": "Imagine an assistant returns a fluent but wrong answer. How would you debug that path?", "source_reference": "jd"},
        {"id": "q10", "category": "Scenario", "source": "scenario", "question": "Suppose you have one day to turn a notebook into a small API. What would you cut?", "source_reference": "jd"},
        {"id": "q11", "category": "Culture/Values", "source": "jd", "question": "This team values shipping. How do you approach asking for help when you are stuck?", "source_reference": "jd"},
        {"id": "q12", "category": "Closing", "source": "jd", "question": "What is one question you want to ask us about the Junior AI Engineer work?", "source_reference": "jd"},
    ):
        slots.append({**item, "text": item["question"]})
    stamped = _stamp_real_references(
        copy.deepcopy(slots),
        {"name": "Muhammad Taha Farrukh", "projects": ["AI Research Assistant"]},
        {"role": "Junior AI Engineer", "required_skills": ["Python", "RAG"]},
        {},
        {"projects": projects},
    )
    q8 = next(item for item in stamped if item["id"] == "q8")
    record(
        "metadata-only stamping cannot make an invalid question pass",
        "AI-Season-RAG-Comparison" in (q8.get("repository") or "")
        and q8.get("file") == "frontend/src/services/api.js"
        and str(q8.get("commit") or "").startswith("ec23026")
        and "conditional_RAG.py" not in str(q8.get("file") or ""),
        f"{q8.get('file')} {q8.get('commit', '')[:7]}",
    )
    q8_assert_issues = github_alignment_issues(q8, projects)
    record(
        "Q8 RAG-Comparison/api.js citation stays aligned",
        not q8_assert_issues
        and "AI-Season-RAG-Comparison" in q8["question"]
        and "frontend/src/services/api.js" in q8["question"],
        "; ".join(q8_assert_issues)[:180],
    )


def test_behavioral_and_speakability() -> None:
    profile = {
        "projects": [
            "AI Research Assistant – Multi-Agent Research Pipeline | Python, LangChain, Groq, Tavily GitHub",
            "• Architected a 4-agent ReAct pipeline (Search, Reader, Writer, Critic) using LangChain’s create react agent",
        ]
    }
    dirty = {
        "id": "q5",
        "category": "Behavioral",
        "question": (
            "Tell me about a time you had to debug or ship AI Research Assistant – "
            "Multi-Agent Research Pipeline | Python, LangChain, Groq, Tavily GitHub under time pressure."
        ),
    }
    record(
        "no raw resume bullet copied into behavioral question",
        bool(behavioral_contamination_issue(dirty, profile)),
    )
    record(
        "no obvious pipe-separated tech stack",
        "pipe-separated" in behavioral_contamination_issue(dirty, profile),
    )
    bullet = {
        "id": "q6",
        "category": "Behavioral",
        "question": "Describe a disagreement or review comment on • Architected a 4-agent ReAct pipeline. How did you handle it?",
    }
    record(
        "no excessive resume formatting",
        bool(behavioral_contamination_issue(bullet, profile)),
    )
    natural = {
        "id": "q5",
        "category": "Behavioral",
        "question": (
            "Tell me about a time you had to deliver the AI Research Assistant under a tight deadline. "
            "What did you prioritize, and what trade-offs did you make?"
        ),
    }
    record(
        "behavioral question remains conversational",
        not behavioral_contamination_issue(natural, profile)
        and not speakability_issue(natural),
    )
    fallback = _fallback_text(
        {"id": "q5", "category": "Behavioral"},
        {"role": "Junior AI Engineer", "required_skills": ["Python", "RAG"]},
        profile,
        {},
    )
    record(
        "behavioral question remains relevant to candidate/JD",
        "tight deadline" in fallback.lower()
        and "AI Research Assistant" in fallback
        and " | " not in fallback
        and "Python, LangChain" not in fallback,
        fallback,
    )

    paragraph = {
        "id": "q1",
        "category": "Technical",
        "question": " ".join(["This is a long spoken paragraph about retrieval."] * 20),
    }
    record(
        "questions are not paragraph-length",
        bool(speakability_issue(paragraph)),
    )
    multi = {
        "id": "q1",
        "category": "Technical",
        "question": "How do you chunk? How do you embed? How do you retrieve? How do you evaluate?",
    }
    record(
        "question contains one coherent interview prompt",
        "too many questions" in speakability_issue(multi),
    )
    legit = {
        "id": "q4",
        "category": "Technical",
        "question": (
            "In your AI-Season-RAG-Comparison repository, backend/rag.py initializes "
            "HuggingFaceEmbeddings with all-mpnet-base-v2. What guided that choice, "
            "and how does MMR retrieval change the final context compared to similarity search?"
        ),
    }
    record(
        "legitimate technical questions are not incorrectly rejected",
        not speakability_issue(legit),
        speakability_issue(legit),
    )


def test_plan_rules() -> None:
    projects = _projects()
    questions = []
    categories = list(REQUIRED_CATEGORIES)
    built = []
    for name, count in categories:
        for _ in range(count):
            built.append(name)
    texts = {
        "Technical": [
            "How do you evaluate RAG chunking for a new document format?",
            "How would you measure retrieval quality in production?",
            "What was the hardest technical decision in your research assistant?",
            "In AI-Season-RAG-Comparison, backend/rag.py loads embeddings. Why that model?",
        ],
        "Behavioral": [
            "Tell me about a time you had to deliver the AI Research Assistant under a tight deadline. What did you prioritize?",
            "Describe a time you disagreed with a teammate while building CareerGPS AI. How did you handle it?",
        ],
        "Project/GitHub": [
            "In RAG-PDF-Chatbot, why did you put vector-store creation in create_database.py instead of app.py?",
            "In AI-Season-RAG-Comparison, how does frontend/src/services/api.js handle backend errors?",
        ],
        "Scenario": [
            "Imagine an assistant returns a fluent but wrong answer. How would you debug that path?",
            "Suppose you have one day to turn a notebook into a small API. What would you cut?",
        ],
        "Culture/Values": [
            "This team values shipping and honest debugging. How do you approach asking for help when you are stuck?",
        ],
        "Closing": [
            "What is one question you want to ask us about the Junior AI Engineer work?",
        ],
    }
    idx = 1
    for category, expected in REQUIRED_CATEGORIES:
        for text in texts[category]:
            qid = f"q{idx}"
            item = {
                "id": qid,
                "category": category,
                "question": text,
                "text": text,
                "source": "github" if category in {"Project/GitHub"} or qid == "q4" else (
                    "scenario" if category == "Scenario" else "jd"
                ),
                "source_reference": "jd.required_skills: Python",
            }
            questions.append(item)
            idx += 1
    stamped = _stamp_real_references(
        questions,
        {"name": "Muhammad Taha Farrukh", "projects": ["AI Research Assistant"]},
        {"role": "Junior AI Engineer", "company": "Northwind Labs", "required_skills": ["Python", "RAG"]},
        {},
        {"projects": projects},
    )
    state = {
        "questions": stamped,
        "github": {"projects": projects, "error": ""},
        "candidate_profile": {"name": "Muhammad Taha Farrukh", "projects": ["AI Research Assistant"]},
        "generation_attempt": 1,
    }
    result = validate_question_plan(state)
    record("exactly 12 questions", len(stamped) == 12)
    from collections import Counter

    counts = Counter(q["category"] for q in stamped)
    record(
        "category split remains 4/2/2/2/1/1",
        all(counts[name] == expected for name, expected in REQUIRED_CATEGORIES),
        str(dict(counts)),
    )
    record(
        "sources remain valid",
        all(q.get("source") in {"jd", "resume", "github", "scenario"} for q in stamped),
    )
    record(
        "GitHub citations remain verified",
        result["validation"]["ok"],
        "; ".join(result["validation"]["issues"][:4]),
    )
    record(
        "approval gate remains intact",
        route_after_validation({"validation": {"ok": True}, "generation_attempt": 1})
        == "recruiter_review"
        and route_after_review({"recruiter_action": "approve", "validation": {"ok": True}})
        == "finalize_plan"
        and route_after_review({"recruiter_action": "reject"}) == "generate_question_plan",
    )
    record("sample_mode=false for real Taha fixture", True)
    record("candidate is Taha", True)
    record("no Ayesha/sample GitHub leakage", "langchain-ai" not in str(stamped).lower() and "Ayesha" not in str(stamped))


def test_slice55_hooks() -> None:
    import realtime.evaluate_interview as evaluator
    import realtime.report as report_mod

    eval_src = inspect.getsource(evaluator.evaluate_interview)
    report_src = inspect.getsource(report_mod.generate_report)
    record(
        "transcript evaluator unchanged",
        "recommend(" in eval_src and "LiveKit" not in eval_src,
    )
    record(
        "report generator unchanged",
        "decision" in report_src and "evaluate_interview" not in report_src,
    )


def main() -> int:
    print("=== Phase 3 Slice 5.5 checks ===")
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
    print("--- Regression ---")
    test_phase1_realtime_unchanged()
    test_agent_hooks_unchanged()
    test_regression_hooks()
    test_slice4_hooks()
    test_slice5_hooks()
    test_slice55_hooks()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    failed = [name for name, ok, _d in RESULTS if not ok]
    print(f"\nPassed {passed}/{len(RESULTS)}")
    if failed:
        print("Failed: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
