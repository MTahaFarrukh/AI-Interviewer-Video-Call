from __future__ import annotations

import logging
import re
from typing import Any

from prep.github_api import (
    GitHubError,
    get_commits_for_path,
    get_file,
    get_readme,
    list_repos,
    list_source_files,
    parse_github_username,
)
from prep.io import write_json
from prep.paths import GITHUB_JSON
from prep.samples import SAMPLE_WARNING, is_sample_github

logger = logging.getLogger("firstround.prep.github")

SKILL_SPLIT = re.compile(r"[^A-Za-z0-9+#]+")
STOPWORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "one",
        "end",
        "our",
        "you",
        "your",
        "this",
        "that",
        "from",
        "into",
        "able",
        "role",
        "must",
        "have",
        "years",
        "year",
        "experience",
        "about",
        "other",
        "such",
        "using",
        "used",
        "work",
        "team",
        "plus",
    }
)


def analyze_github(github_url: str, jd: dict[str, Any]) -> dict[str, Any]:
    username = parse_github_username(github_url)
    sample_mode = is_sample_github(username)
    if sample_mode:
        logger.warning(SAMPLE_WARNING)
    try:
        repos = list_repos(username)
    except GitHubError as exc:
        payload = {
            "username": username,
            "url": f"https://github.com/{username}",
            "error": str(exc),
            "repos_considered": 0,
            "projects": [],
            "sample_mode": sample_mode,
        }
        write_json(GITHUB_JSON, payload)
        return payload

    ranked = _rank_repos(repos, jd)
    selected = ranked[:3]
    projects: list[dict[str, Any]] = []
    for repo in selected:
        owner = str((repo.get("owner") or {}).get("login") or username)
        if owner.lower() != username.lower():
            continue
        projects.append(_enrich_repo(repo, jd))

    payload = {
        "username": username,
        "url": f"https://github.com/{username}",
        "error": "",
        "repos_considered": len(repos),
        "ranked_names": [item["name"] for item in ranked[:8]],
        "projects": projects,
        "sample_mode": sample_mode,
    }
    if sample_mode:
        payload["warning"] = SAMPLE_WARNING
    write_json(GITHUB_JSON, payload)
    return payload


def _rank_repos(repos: list[dict[str, Any]], jd: dict[str, Any]) -> list[dict[str, Any]]:
    terms = _jd_terms(jd)
    scored: list[tuple[float, dict[str, Any]]] = []
    for repo in repos:
        if repo.get("archived"):
            continue
        blob = " ".join(
            [
                str(repo.get("name") or ""),
                str(repo.get("description") or ""),
                " ".join(repo.get("topics") or []),
                str(repo.get("language") or ""),
            ]
        ).lower()
        score = 0.0
        for term in terms:
            if term in blob:
                score += 3.0
        language = str(repo.get("language") or "").lower()
        if language and language in terms:
            score += 2.0
        if repo.get("fork"):
            score -= 1.5
        score += min(float(repo.get("stargazers_count") or 0) / 5000.0, 0.3)
        scored.append((score, repo))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [repo for _score, repo in scored]


def _enrich_repo(repo: dict[str, Any], jd: dict[str, Any]) -> dict[str, Any]:
    owner = str((repo.get("owner") or {}).get("login") or "")
    name = str(repo.get("name") or "")
    branch = str(repo.get("default_branch") or "main")
    readme = get_readme(owner, name)
    files = list_source_files(owner, name, branch)
    chosen_files = _pick_files(files, jd)[:2]
    file_payloads = [get_file(owner, name, path) for path in chosen_files]
    file_payloads = [item for item in file_payloads if item.get("missing") != "true" and item.get("text")]
    primary = file_payloads[0] if file_payloads else {"path": readme.get("path") or "", "text": ""}
    file_path = str(primary.get("path") or "")
    file_commits = get_commits_for_path(owner, name, file_path) if file_path else []
    commit = file_commits[0] if file_commits else {"sha": "", "message": ""}
    evidence_bits = []
    if readme.get("text"):
        evidence_bits.append(readme["text"][:400])
    if primary.get("text"):
        evidence_bits.append(primary["text"][:400])
    if commit.get("sha") and commit.get("message"):
        evidence_bits.append(f"commit {commit['sha'][:7]} touched {file_path}: {commit['message']}")
    source_url = ""
    if file_path and commit.get("sha"):
        source_url = f"https://github.com/{owner}/{name}/blob/{commit['sha']}/{file_path}"
    elif file_path:
        source_url = f"https://github.com/{owner}/{name}/blob/{branch}/{file_path}"
    return {
        "name": name,
        "full_name": str(repo.get("full_name") or f"{owner}/{name}"),
        "url": str(repo.get("html_url") or f"https://github.com/{owner}/{name}"),
        "description": str(repo.get("description") or ""),
        "language": str(repo.get("language") or ""),
        "stars": int(repo.get("stargazers_count") or 0),
        "default_branch": branch,
        "readme_path": readme.get("path") or "",
        "readme_excerpt": (readme.get("text") or "")[:800],
        "file_path": file_path,
        "file_excerpt": (primary.get("text") or "")[:800],
        "files": [{"path": item["path"], "excerpt": item["text"][:400]} for item in file_payloads],
        "commit_sha": commit.get("sha") or "",
        "commit_message": commit.get("message") or "",
        "commit_verified": bool(commit.get("sha")),
        "source_url": source_url,
        "commits": file_commits[:3],
        "why_relevant": _why_relevant(repo, jd),
        "evidence": " | ".join(bit for bit in evidence_bits if bit)[:900],
    }


def _pick_files(files: list[str], jd: dict[str, Any]) -> list[str]:
    terms = _jd_terms(jd)
    ranked: list[tuple[int, str]] = []
    for path in files:
        lowered = path.lower()
        if any(part in lowered for part in (".github/", "conformance", "/tests/", "/test/", "/docs/", "examples/")):
            continue
        score = 0
        for term in terms:
            if term in lowered:
                score += 2
        if lowered.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
            score += 1
        if any(part in lowered for part in ("src/", "lib/", "app/")):
            score += 1
        if any(part in lowered for part in ("test", "spec", "example", "docs/")):
            score -= 1
        ranked.append((score, path))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [path for _score, path in ranked]


def _jd_terms(jd: dict[str, Any]) -> set[str]:
    blobs = []
    for key in (
        "required_skills",
        "preferred_skills",
        "technologies",
        "domain_knowledge",
        "competencies",
        "responsibilities",
    ):
        blobs.extend(jd.get(key) or [])
    blobs.append(str(jd.get("role") or ""))
    terms: set[str] = set()
    for blob in blobs:
        for token in SKILL_SPLIT.split(str(blob).lower()):
            if len(token) >= 3 and token not in STOPWORDS:
                terms.add(token)
    return terms


def _why_relevant(repo: dict[str, Any], jd: dict[str, Any]) -> str:
    language = str(repo.get("language") or "unknown")
    role = str(jd.get("role") or "the role")
    desc = str(repo.get("description") or "no description provided")
    return (
        f"{repo.get('name')} is written mainly in {language} and matches {role} "
        f"requirements. GitHub description: {desc}"
    )
