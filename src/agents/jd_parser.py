from __future__ import annotations

from pathlib import Path
from typing import Any

from prep.heuristic import merge_structured, parse_jd_heuristic
from prep.io import write_json
from prep.llm import LlmError, generate_json
from prep.paths import JD_JSON, PROMPTS_DIR
from prep.pdf import extract_text


def parse_jd_file(path: Path) -> dict[str, Any]:
    raw_text, extractor = extract_text(path)
    structured = merge_structured(parse_jd_heuristic(raw_text), _llm_jd(raw_text))
    structured["raw_text"] = raw_text[:8000]
    structured["extractor"] = extractor
    structured["source_path"] = str(path)
    write_json(JD_JSON, structured)
    return structured


def _llm_jd(text: str) -> dict[str, Any]:
    template = (PROMPTS_DIR / "parse_jd.md").read_text(encoding="utf-8")
    prompt = template.replace("{{JD_TEXT}}", text[:12000])
    try:
        data = generate_json(prompt, temperature=0.1)
    except LlmError as exc:
        return {
            "role": "",
            "company": "",
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "experience_requirements": [],
            "technologies": [],
            "domain_knowledge": [],
            "competencies": [],
            "seniority": "",
            "other": [],
            "parse_error": str(exc),
            "needs_review": True,
        }
    if not isinstance(data, dict):
        raise LlmError("JD parser did not return an object")
    return {
        "role": str(data.get("role") or "").strip(),
        "company": str(data.get("company") or "").strip(),
        "required_skills": _as_str_list(data.get("required_skills")),
        "preferred_skills": _as_str_list(data.get("preferred_skills")),
        "responsibilities": _as_str_list(data.get("responsibilities")),
        "experience_requirements": _as_str_list(data.get("experience_requirements")),
        "technologies": _as_str_list(data.get("technologies")),
        "domain_knowledge": _as_str_list(data.get("domain_knowledge")),
        "competencies": _as_str_list(data.get("competencies")),
        "seniority": str(data.get("seniority") or "").strip(),
        "other": _as_str_list(data.get("other")),
        "needs_review": bool(data.get("needs_review")),
    }


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]
