"""Lightweight semantic, grounding, and speakability checks for interview questions."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

ALLOWED_SOURCES = frozenset({"jd", "resume", "github", "scenario"})

BEHAVIORAL_RE = re.compile(
    r"\b(tell me about a time|describe a time|describe a disagreement|"
    r"when you|how did you (handle|respond|work|deal|react)|"
    r"conflict|disagreement|team(work|mate)?s?|collaborat|"
    r"failure|mistake|feedback|leader|mentor|learned|"
    r"under pressure|tight deadline|stakeholder|review comment)\b",
    re.I,
)
SCENARIO_RE = re.compile(
    r"\b(imagine|suppose|what would you do|how would you|"
    r"if you (had|were|joined)|you (inherit|are asked)|"
    r"one day to)\b",
    re.I,
)
CULTURE_RE = re.compile(
    r"\b(work style|values|culture|how do you (approach|give|receive|handle being)|"
    r"code review|pull request|honest|shipping|when you('re| are) stuck|"
    r"ask(ing)? for help|feedback in a|collaboration)\b",
    re.I,
)
CLOSING_RE = re.compile(
    r"\b(question you (want|would like) to ask|questions for (us|me|the team)|"
    r"what would you like to know|anything (else )?you'd like|"
    r"wrap up|closing)\b",
    re.I,
)
GITHUB_RE = re.compile(
    r"\b(repositor(y|ies)|repo|github|commit|file|codebase|pull request|readme)\b",
    re.I,
)
FILE_RE = re.compile(r"\b[\w./\\-]+\.(?:py|js|jsx|ts|tsx|go|java|rb|rs|md)\b", re.I)
PIPE_RE = re.compile(r"\s\|\s")
BULLET_RE = re.compile(r"[•·▪►]|^\s*[-*]\s", re.M)
RESUME_LABEL_RE = re.compile(
    r"\b(honors & awards|extracurricular|additional projects|work experience|"
    r"technical skills|languages spoken|volunteer,|youtube educator)\b",
    re.I,
)
COLON_RESUME_RE = re.compile(
    r":\s*(architected|implemented|developed|built|designed|created|won)\b",
    re.I,
)
TECH_STACK_RE = re.compile(
    r"\b(?:python|javascript|typescript|langchain|langgraph|fastapi|react|"
    r"node\.?js|groq|tavily|chroma(?:db)?|mysql|sqlite|streamlit)"
    r"(?:\s*,\s*(?:python|javascript|typescript|langchain|langgraph|fastapi|"
    r"react|node\.?js|groq|tavily|chroma(?:db)?|mysql|sqlite|streamlit)){2,}\b",
    re.I,
)

MAX_QUESTION_CHARS = 480
MAX_SENTENCES = 4
MAX_QUESTION_MARKS = 2
MAX_RESUME_FRAGMENT = 48


def normalize_source(value: str, category: str) -> str:
    source = (value or "").strip().lower()
    if source == "gap_analysis":
        source = "jd" if category in {"Technical", "Scenario", "Culture/Values", "Closing"} else "resume"
    if source not in ALLOWED_SOURCES:
        defaults = {
            "Technical": "jd",
            "Behavioral": "resume",
            "Project/GitHub": "github",
            "Scenario": "scenario",
            "Culture/Values": "jd",
            "Closing": "jd",
        }
        source = defaults.get(category, "jd")
    if category == "Scenario":
        source = "scenario"
    if category == "Project/GitHub":
        source = "github"
    return source


def question_text(question: dict[str, Any]) -> str:
    return str(question.get("question") or question.get("text") or "").strip()


def flatten_source_reference(value: Any) -> str:
    if isinstance(value, dict):
        repo = str(value.get("repository") or "").strip()
        path = str(value.get("file") or "").strip()
        commit = str(value.get("commit") or "").strip()
        parts = [part for part in (repo, path) if part]
        ref = "/".join(parts)
        if commit:
            ref = f"{ref}@{commit[:7]}" if ref else commit[:7]
        return ref
    return str(value or "").strip()


def short_project_name(raw: str) -> str:
    text = str(raw or "").strip()
    text = PIPE_RE.split(text)[0]
    text = re.split(r"\s+[–—]\s+", text)[0]
    text = text.split(":")[0]
    text = re.sub(r"\s+", " ", text).strip(" -–—•")
    if len(text) > 60:
        text = text[:57].rsplit(" ", 1)[0]
    return text


def semantic_issue(question: dict[str, Any]) -> str:
    category = str(question.get("category") or "")
    text = question_text(question)
    if category == "Behavioral" and not BEHAVIORAL_RE.search(text):
        return f"{question.get('id')} is labeled Behavioral but does not ask about past behavior or experience."
    if category == "Scenario" and not SCENARIO_RE.search(text):
        return f"{question.get('id')} is labeled Scenario but does not present a hypothetical situation."
    if category == "Culture/Values" and not CULTURE_RE.search(text):
        return f"{question.get('id')} is labeled Culture/Values but does not assess work style or values."
    if category == "Closing" and not CLOSING_RE.search(text):
        return f"{question.get('id')} is labeled Closing but is not a closing interview question."
    if category == "Project/GitHub":
        if not (question.get("repository") or GITHUB_RE.search(text)):
            return f"{question.get('id')} is labeled Project/GitHub but is not about a repository or project."
    return ""


def speakability_issue(question: dict[str, Any]) -> str:
    text = question_text(question)
    qid = question.get("id")
    if not text:
        return f"{qid} is empty."
    if len(text) > MAX_QUESTION_CHARS:
        return f"{qid} is too long to speak as one interview question."
    sentences = [part for part in re.split(r"[.!?]+", text) if part.strip()]
    if len(sentences) > MAX_SENTENCES:
        return f"{qid} reads as a paragraph rather than one spoken question."
    if text.count("?") > MAX_QUESTION_MARKS:
        return f"{qid} asks too many questions at once."
    return ""


def behavioral_contamination_issue(question: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    if str(question.get("category") or "") != "Behavioral":
        return ""
    text = question_text(question)
    qid = question.get("id")
    if PIPE_RE.search(text):
        return f"{qid} copies pipe-separated resume formatting into a spoken question."
    if BULLET_RE.search(text):
        return f"{qid} copies bullet formatting into a spoken question."
    if RESUME_LABEL_RE.search(text):
        return f"{qid} copies a resume section label into a spoken question."
    if TECH_STACK_RE.search(text):
        return f"{qid} copies a technology-stack fragment into a spoken question."
    if COLON_RESUME_RE.search(text):
        return f"{qid} copies a resume achievement fragment into a spoken question."
    for fragment in _resume_fragments(profile or {}):
        if fragment.lower() in text.lower():
            return f"{qid} copies a raw resume bullet into a spoken question."
    return ""


def github_alignment_issues(
    question: dict[str, Any],
    projects: list[dict[str, Any]] | None = None,
) -> list[str]:
    source = normalize_source(str(question.get("source") or ""), str(question.get("category") or ""))
    if str(question.get("category") or "") != "Project/GitHub" and source != "github":
        return []
    projects = [item for item in (projects or []) if isinstance(item, dict)]
    qid = str(question.get("id") or "")
    text = question_text(question)
    cited_repo = str(question.get("repository") or "").strip()
    cited_file = str(question.get("file") or "").replace("\\", "/").strip()
    cited_commit = str(question.get("commit") or "").strip()
    issues: list[str] = []
    cited_project = _match_project(cited_repo, projects) if cited_repo else None

    if cited_repo and projects and cited_project is None:
        issues.append(f"{qid} cites repository {cited_repo} that is not in approved GitHub evidence.")
    named_projects = _named_projects(text, projects)
    if named_projects and cited_project is not None:
        if not any(_same_project(item, cited_project) for item in named_projects):
            names = ", ".join(_project_name(item) for item in named_projects)
            issues.append(
                f"{qid} names {names} but citation points to {_project_name(cited_project)}."
            )
    named_files = _named_files(text, projects)
    if cited_file and named_files:
        named_paths = {_norm_path(path) for _proj, path in named_files}
        if _norm_path(cited_file) not in named_paths and PurePosixPath(cited_file).name.lower() not in {
            PurePosixPath(path).name.lower() for path in named_paths
        }:
            issues.append(
                f"{qid} names file {sorted(named_paths)[0]} but citation points to {cited_file}."
            )
    if cited_file and named_files:
        file_projects = [proj for proj, path in named_files if _norm_path(path) == _norm_path(cited_file)]
        if file_projects and cited_project is not None:
            if not any(_same_project(item, cited_project) for item in file_projects):
                issues.append(
                    f"{qid} names a file from {_project_name(file_projects[0])} "
                    f"but citation points to {_project_name(cited_project)}."
                )
    if cited_project is not None and cited_file:
        allowed_files = {_norm_path(path) for path in _project_files(cited_project)}
        if allowed_files and _norm_path(cited_file) not in allowed_files:
            issues.append(f"{qid} file {cited_file} is not in approved GitHub evidence for that repository.")
    if cited_project is not None and cited_commit:
        allowed_commits = _project_commits(cited_project)
        if allowed_commits and not any(
            cited_commit.lower().startswith(item.lower()) or item.lower().startswith(cited_commit.lower())
            for item in allowed_commits
        ):
            issues.append(f"{qid} commit does not match approved GitHub evidence.")
    return issues


def question_quality_issues(
    question: dict[str, Any],
    *,
    projects: list[dict[str, Any]] | None = None,
    profile: dict[str, Any] | None = None,
) -> list[str]:
    issues: list[str] = []
    semantic = semantic_issue(question)
    if semantic:
        issues.append(semantic)
    speak = speakability_issue(question)
    if speak:
        issues.append(speak)
    contamination = behavioral_contamination_issue(question, profile)
    if contamination:
        issues.append(contamination)
    issues.extend(github_alignment_issues(question, projects))
    return issues


def _resume_fragments(profile: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in ("projects", "experience", "other"):
        for item in profile.get(key) or []:
            text = str(item or "").strip()
            if len(text) < MAX_RESUME_FRAGMENT:
                continue
            if PIPE_RE.search(text) or BULLET_RE.search(text) or " – " in text or " — " in text:
                fragments.append(text)
    return fragments


def _norm_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().lower()


def _project_name(project: dict[str, Any]) -> str:
    return str(project.get("name") or project.get("full_name") or "").strip()


def _project_aliases(project: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for raw in (
        project.get("name"),
        project.get("full_name"),
        project.get("url"),
    ):
        text = str(raw or "").strip().rstrip("/").lower()
        if not text:
            continue
        aliases.append(text)
        aliases.append(text.replace("https://github.com/", ""))
        if "/" in text.replace("https://github.com/", ""):
            aliases.append(text.replace("https://github.com/", "").split("/")[-1])
    seen: set[str] = set()
    out: list[str] = []
    for alias in aliases:
        if alias and alias not in seen:
            seen.add(alias)
            out.append(alias)
    return out


def _same_project(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_names = set(_project_aliases(left))
    right_names = set(_project_aliases(right))
    return bool(left_names & right_names)


def _match_project(repo: str, projects: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = str(repo or "").strip().rstrip("/").lower().replace("https://github.com/", "")
    if not needle:
        return None
    for project in projects:
        aliases = _project_aliases(project)
        if needle in aliases or any(needle in alias or alias in needle for alias in aliases if len(alias) >= 4):
            return project
    return None


def _project_files(project: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    if project.get("file_path"):
        paths.append(str(project["file_path"]))
    if project.get("readme_path"):
        paths.append(str(project["readme_path"]))
    for item in project.get("files") or []:
        if isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
        elif isinstance(item, str):
            paths.append(item)
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        key = _norm_path(path)
        if key and key not in seen:
            seen.add(key)
            out.append(path.replace("\\", "/"))
    return out


def _project_commits(project: dict[str, Any]) -> list[str]:
    shas: list[str] = []
    if project.get("commit_sha"):
        shas.append(str(project["commit_sha"]))
    for item in project.get("commits") or []:
        if isinstance(item, dict) and item.get("sha"):
            shas.append(str(item["sha"]))
        elif isinstance(item, str):
            shas.append(item)
    return [sha for sha in shas if sha]


def _named_projects(text: str, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blob = text.lower()
    found: list[dict[str, Any]] = []
    for project in projects:
        aliases = sorted(_project_aliases(project), key=len, reverse=True)
        if any(len(alias) >= 4 and alias in blob for alias in aliases):
            found.append(project)
    return found


def _named_files(text: str, projects: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    blob = text.replace("\\", "/").lower()
    found: list[tuple[dict[str, Any], str]] = []
    basename_index: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for project in projects:
        for path in _project_files(project):
            norm = _norm_path(path)
            base = PurePosixPath(norm).name
            basename_index.setdefault(base, []).append((project, path))
            if norm and norm in blob:
                found.append((project, path))
    for match in FILE_RE.finditer(text.replace("\\", "/")):
        base = PurePosixPath(match.group(0).replace("\\", "/")).name.lower()
        hits = basename_index.get(base) or []
        if len(hits) == 1:
            found.extend(hits)
    unique: list[tuple[dict[str, Any], str]] = []
    seen: set[tuple[str, str]] = set()
    for project, path in found:
        key = (_project_name(project).lower(), _norm_path(path))
        if key not in seen:
            seen.add(key)
            unique.append((project, path))
    return unique


def match_question_to_project(
    question: dict[str, Any],
    projects: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """Return (project, preferred_file) named by the question text."""
    text = question_text(question)
    named_projects = _named_projects(text, projects)
    named_files = _named_files(text, projects)
    if named_files:
        if named_projects:
            for project, path in named_files:
                if any(_same_project(project, named) for named in named_projects):
                    return project, path
        return named_files[0]
    if named_projects:
        project = named_projects[0]
        return project, str(project.get("file_path") or "")
    return None, ""
