from __future__ import annotations

from typing import Any

from prep.io import write_json
from prep.paths import PROFILE_JSON


def build_candidate_profile(state: dict[str, Any]) -> dict[str, Any]:
    resume = state.get("resume") or {}
    github_url = str(state.get("github_url_override") or resume.get("github_url") or state.get("github_url") or "")
    profile = {
        "name": resume.get("name") or "",
        "email": resume.get("email") or "",
        "github_url": github_url,
        "education": list(resume.get("education") or []),
        "experience": list(resume.get("experience") or []),
        "skills": list(resume.get("skills") or []),
        "projects": list(resume.get("projects") or []),
        "certifications": list(resume.get("certifications") or []),
        "other": list(resume.get("other") or []),
        "extractor": resume.get("extractor") or "",
    }
    write_json(PROFILE_JSON, profile)
    return {"candidate_profile": profile, "github_url": github_url}
