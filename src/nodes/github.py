from __future__ import annotations

from typing import Any

from agents.github_agent import analyze_github
from prep.github_api import GitHubError, parse_github_username
from prep.samples import SAMPLE_WARNING, is_sample_github


def extract_github(state: dict[str, Any]) -> dict[str, Any]:
    url = str(state.get("github_url_override") or state.get("github_url") or "").strip()
    if not url:
        return {
            "github_username": "",
            "github_error": "No GitHub URL found in the resume or CLI override.",
            "github": {
                "username": "",
                "url": "",
                "error": "No GitHub URL found in the resume or CLI override.",
                "repos_considered": 0,
                "projects": [],
            },
        }
    try:
        username = parse_github_username(url)
    except GitHubError as exc:
        return {
            "github_username": "",
            "github_error": str(exc),
            "github": {
                "username": "",
                "url": url,
                "error": str(exc),
                "repos_considered": 0,
                "projects": [],
            },
        }
    warning = SAMPLE_WARNING if is_sample_github(username) else ""
    return {
        "github_username": username,
        "github_url": f"https://github.com/{username}",
        "github_error": "",
        "sample_mode": is_sample_github(username),
        "warnings": [warning] if warning else [],
    }


def analyze_github_node(state: dict[str, Any]) -> dict[str, Any]:
    url = str(state.get("github_url") or "").strip()
    jd = state.get("jd") or {}
    github = analyze_github(url, jd)
    error = str(github.get("error") or "")
    warnings = []
    if error:
        warnings.append(error)
    if not github.get("projects"):
        warnings.append("GitHub analysis returned no projects.")
    return {
        "github": github,
        "github_error": error,
        "github_projects": github.get("projects") or [],
        "sample_mode": bool(github.get("sample_mode")),
        "warnings": warnings,
    }
