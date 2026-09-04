"""Grounded, non-LLM extraction from resume/JD text. Does not invent facts."""

from __future__ import annotations

import re
from typing import Any

from prep.pdf import find_emails, find_github_urls

SECTION_ALIASES = {
    "summary": "summary",
    "objective": "summary",
    "education": "education",
    "experience": "experience",
    "work experience": "experience",
    "skills": "skills",
    "technical skills": "skills",
    "projects": "projects",
    "certifications": "certifications",
    "certification": "certifications",
}

JD_SECTION_ALIASES = {
    "must-haves": "required_skills",
    "must haves": "required_skills",
    "required": "required_skills",
    "requirements": "required_skills",
    "nice to have": "preferred_skills",
    "nice-to-have": "preferred_skills",
    "preferred": "preferred_skills",
    "responsibilities": "responsibilities",
    "about the role": "about",
    "assessed competencies": "competencies",
    "competencies": "competencies",
}


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" -\t")


def _normalize_lines(text: str) -> list[str]:
    return [_clean(line) for line in (text or "").splitlines()]


def parse_resume_heuristic(text: str) -> dict[str, Any]:
    lines = _normalize_lines(text)
    compact = [line for line in lines if line]
    sections: dict[str, list[str]] = {key: [] for key in ("summary", "education", "experience", "skills", "projects", "certifications")}
    current = ""
    name = ""
    for line in compact:
        key = SECTION_ALIASES.get(line.lower().rstrip(":"))
        if key:
            current = key
            continue
        if not name and not key:
            name = line
            continue
        if current:
            sections[current].append(line)

    skills: list[str] = []
    for item in sections["skills"]:
        skills.extend(part.strip() for part in re.split(r"[,;/]", item) if part.strip())

    github_urls = find_github_urls(text)
    emails = find_emails(text)
    return {
        "name": name,
        "email": emails[0] if emails else "",
        "github_url": github_urls[0] if github_urls else "",
        "education": sections["education"],
        "experience": sections["experience"],
        "skills": list(dict.fromkeys(skills)),
        "projects": [item.lstrip("- ") for item in sections["projects"]],
        "certifications": sections["certifications"],
        "other": sections["summary"],
        "needs_review": False,
        "parser": "heuristic",
    }


def parse_jd_heuristic(text: str) -> dict[str, Any]:
    lines = [line for line in _normalize_lines(text) if line]
    role = lines[0] if lines else ""
    company = ""
    seniority = ""
    if len(lines) > 1:
        company = lines[1]
    if len(lines) > 2 and re.search(r"year|junior|senior|intern", lines[2], re.I):
        seniority = lines[2]

    sections: dict[str, list[str]] = {
        "required_skills": [],
        "preferred_skills": [],
        "responsibilities": [],
        "competencies": [],
        "about": [],
    }
    current = ""
    skip_headers = {role.lower(), company.lower(), seniority.lower()}
    for line in lines:
        key = JD_SECTION_ALIASES.get(line.lower().rstrip(":"))
        if key:
            current = key
            continue
        if line.lower() in skip_headers:
            continue
        if current:
            sections.setdefault(current, []).append(line.lstrip("- "))

    required = sections["required_skills"] or _split_keywords(" ".join(sections["about"]))
    technologies = []
    for item in required + sections["preferred_skills"]:
        for token in ("Python", "LangChain", "LangGraph", "RAG", "Git", "REST", "FastAPI", "SQLite"):
            if token.lower() in item.lower():
                technologies.append(token)
    return {
        "role": role,
        "company": company.split(",")[0].strip() if company else "",
        "required_skills": required,
        "preferred_skills": sections["preferred_skills"],
        "responsibilities": sections["responsibilities"],
        "experience_requirements": [seniority] if seniority else [],
        "technologies": list(dict.fromkeys(technologies)),
        "domain_knowledge": [item for item in required if re.search(r"RAG|LLM|retrieval|Lang", item, re.I)],
        "competencies": sections["competencies"],
        "seniority": seniority,
        "other": sections["about"][:4],
        "needs_review": False,
        "parser": "heuristic",
    }


def merge_structured(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in {"parse_error", "needs_review", "parser"}:
            continue
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()
        elif isinstance(value, list) and value:
            merged[key] = value
    if overlay.get("parse_error"):
        merged["llm_error"] = "gemini_structured_output_failed"
        merged["needs_review"] = True
    return merged


def _split_keywords(text: str) -> list[str]:
    parts = re.split(r"[,;]| and ", text)
    return [part.strip(" .") for part in parts if 2 < len(part.strip()) < 80]
