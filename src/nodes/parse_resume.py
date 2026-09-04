from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.resume_parser import parse_resume_file


def parse_resume(state: dict[str, Any]) -> dict[str, Any]:
    resume = parse_resume_file(Path(state["resume_path"]))
    warnings = []
    if resume.get("needs_review") or resume.get("parse_error"):
        warnings.append("Resume structured parse needed review or used a fallback.")
    if not resume.get("name"):
        warnings.append("Resume parser could not find a candidate name.")
    return {"resume": resume, "warnings": warnings}
