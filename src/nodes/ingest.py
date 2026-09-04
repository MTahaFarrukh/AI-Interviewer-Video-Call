from __future__ import annotations

from pathlib import Path
from typing import Any

from prep.paths import ensure_output_dirs
from prep.pdf import PdfExtractError, extract_text, find_github_urls


def ingest_inputs(state: dict[str, Any]) -> dict[str, Any]:
    ensure_output_dirs()
    resume_path = Path(state["resume_path"])
    jd_path = Path(state["jd_path"])
    errors: list[str] = []
    warnings: list[str] = []

    try:
        resume_text, resume_extractor = extract_text(resume_path)
    except PdfExtractError as exc:
        raise PdfExtractError(str(exc)) from exc

    try:
        jd_text, jd_extractor = extract_text(jd_path)
    except PdfExtractError as exc:
        raise PdfExtractError(str(exc)) from exc

    github_urls = find_github_urls(resume_text)
    override = str(state.get("github_url_override") or "").strip()
    return {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "resume_extractor": resume_extractor,
        "jd_extractor": jd_extractor,
        "github_urls_found": github_urls,
        "github_url": override or (github_urls[0] if github_urls else ""),
        "generation_attempt": 0,
        "approval_status": "pending",
        "errors": errors,
        "warnings": warnings,
    }
