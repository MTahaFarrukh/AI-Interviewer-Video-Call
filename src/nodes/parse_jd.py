from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.jd_parser import parse_jd_file


def parse_jd(state: dict[str, Any]) -> dict[str, Any]:
    jd = parse_jd_file(Path(state["jd_path"]))
    warnings = []
    if jd.get("needs_review") or jd.get("parse_error"):
        warnings.append("JD structured parse needed review or used a fallback.")
    if not jd.get("role"):
        warnings.append("JD parser could not find a role title.")
    return {"jd": jd, "warnings": warnings}
