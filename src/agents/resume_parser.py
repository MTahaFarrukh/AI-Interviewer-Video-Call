from __future__ import annotations

from pathlib import Path
from typing import Any

from prep.heuristic import merge_structured, parse_resume_heuristic
from prep.io import write_json
from prep.llm import LlmError, generate_json
from prep.paths import PROMPTS_DIR, RESUME_JSON
from prep.pdf import extract_text, find_emails, find_github_urls, redact_private_fields


def parse_resume_file(path: Path) -> dict[str, Any]:
    raw_text, extractor = extract_text(path)
    redacted = redact_private_fields(raw_text)
    github_urls = find_github_urls(redacted)
    emails = find_emails(redacted)
    structured = merge_structured(parse_resume_heuristic(redacted), _llm_resume(redacted))
    structured["raw_text"] = redacted[:8000]
    structured["extractor"] = extractor
    structured["source_path"] = str(path)
    if github_urls and not structured.get("github_url"):
        structured["github_url"] = github_urls[0]
    if emails and not structured.get("email"):
        structured["email"] = emails[0]
    structured["github_urls_found"] = github_urls
    write_json(RESUME_JSON, structured)
    return structured


def _llm_resume(text: str) -> dict[str, Any]:
    template = (PROMPTS_DIR / "parse_resume.md").read_text(encoding="utf-8")
    prompt = template.replace("{{RESUME_TEXT}}", text[:12000])
    try:
        data = generate_json(prompt, temperature=0.1)
    except LlmError as exc:
        return {
            "name": "",
            "email": "",
            "github_url": "",
            "education": [],
            "experience": [],
            "skills": [],
            "projects": [],
            "certifications": [],
            "other": [],
            "parse_error": str(exc),
            "needs_review": True,
        }
    if not isinstance(data, dict):
        raise LlmError("Resume parser did not return an object")
    return {
        "name": str(data.get("name") or "").strip(),
        "email": str(data.get("email") or "").strip(),
        "github_url": str(data.get("github_url") or "").strip(),
        "education": _as_str_list(data.get("education")),
        "experience": _as_str_list(data.get("experience")),
        "skills": _as_str_list(data.get("skills")),
        "projects": _as_str_list(data.get("projects")),
        "certifications": _as_str_list(data.get("certifications")),
        "other": _as_str_list(data.get("other")),
        "needs_review": bool(data.get("needs_review")),
    }


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]
