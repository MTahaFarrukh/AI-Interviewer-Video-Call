from __future__ import annotations

from collections import Counter
from typing import Any

from agents.question_planner import REQUIRED_CATEGORIES
from prep.banned import banned_hits
from prep.github_api import commit_touches_file, parse_owner_repo
from prep.question_quality import (
    ALLOWED_SOURCES,
    flatten_source_reference,
    normalize_source,
    question_quality_issues,
)


def validate_question_plan(state: dict[str, Any]) -> dict[str, Any]:
    questions = list(state.get("questions") or [])
    issues: list[str] = []
    github = state.get("github") or {}
    projects = github.get("projects") or state.get("github_projects") or []
    profile = state.get("candidate_profile") or {}

    if len(questions) != 12:
        issues.append(f"Expected exactly 12 questions, got {len(questions)}.")

    counts = Counter(str(q.get("category") or "") for q in questions)
    for category, expected in REQUIRED_CATEGORIES:
        actual = counts.get(category, 0)
        if actual != expected:
            issues.append(f"Category {category} should have {expected}, got {actual}.")

    texts = [str(q.get("question") or q.get("text") or "").strip().lower() for q in questions]
    if any(not text for text in texts):
        issues.append("One or more questions are empty.")
    if len({t for t in texts if t}) != len([t for t in texts if t]):
        issues.append("Duplicate question text detected.")

    for question in questions:
        text = str(question.get("question") or "")
        hits = banned_hits(text)
        if hits:
            issues.append(f"{question.get('id')} hits banned topics: {', '.join(hits)}.")
        source = normalize_source(str(question.get("source") or ""), str(question.get("category") or ""))
        if str(question.get("source") or "") not in ALLOWED_SOURCES:
            issues.append(f"{question.get('id')} has invalid source {question.get('source')!r}.")
        question["source"] = source
        question["source_type"] = source
        question["source_reference"] = flatten_source_reference(question.get("source_reference"))
        if not str(question.get("source_reference") or "").strip():
            issues.append(f"{question.get('id')} is missing a source_reference.")
        for issue in question_quality_issues(question, projects=projects, profile=profile):
            issues.append(issue)
        if question.get("category") == "Project/GitHub" or source == "github":
            if not question.get("repository"):
                issues.append(f"{question.get('id')} is a GitHub question without a repository.")
            if not (question.get("file") or question.get("evidence")):
                issues.append(f"{question.get('id')} is a GitHub question without file or evidence.")
            commit_issue = _commit_issue(question, projects)
            if commit_issue and commit_issue not in issues:
                issues.append(commit_issue)

    github_cited = [
        q
        for q in questions
        if str(q.get("source") or "") == "github" and q.get("repository") and q.get("source_reference")
    ]
    if projects and len(github_cited) < 3:
        issues.append(f"Need at least 3 GitHub-cited questions, found {len(github_cited)}.")
    if not projects and not github.get("error"):
        issues.append("No GitHub projects available to ground project questions.")

    validation = {
        "ok": not issues,
        "issues": issues,
        "github_cited": len(github_cited),
        "attempt": int(state.get("generation_attempt") or 0),
    }
    return {"validation": validation, "questions": questions}


def _commit_issue(question: dict[str, Any], projects: list[dict[str, Any]]) -> str:
    sha = str(question.get("commit") or "").strip()
    path = str(question.get("file") or "").replace("\\", "/").strip()
    if not sha:
        return ""
    if not path:
        return f"{question.get('id')} cites a commit without a file path."
    for project in projects:
        files = [str(project.get("file_path") or "").replace("\\", "/")]
        for item in project.get("files") or []:
            if isinstance(item, dict) and item.get("path"):
                files.append(str(item["path"]).replace("\\", "/"))
        shas = [str(project.get("commit_sha") or "")]
        for item in project.get("commits") or []:
            if isinstance(item, dict) and item.get("sha"):
                shas.append(str(item["sha"]))
        if path in files and sha in shas and project.get("commit_verified"):
            return ""
    owner, repo = parse_owner_repo(str(question.get("repository") or ""))
    if owner and repo and commit_touches_file(owner, repo, path, sha):
        return ""
    return f"{question.get('id')} commit does not belong to file {path}."
