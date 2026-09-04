from __future__ import annotations

import json
from typing import Any

from prep.io import write_json
from prep.llm import LlmError, generate_json
from prep.paths import GAP_JSON, PROMPTS_DIR


def gap_analysis(state: dict[str, Any]) -> dict[str, Any]:
    profile = state.get("candidate_profile") or {}
    jd = {k: v for k, v in (state.get("jd") or {}).items() if k != "raw_text"}
    template = (PROMPTS_DIR / "gap_analysis.md").read_text(encoding="utf-8")
    prompt = template.replace(
        "{{CONTEXT_JSON}}",
        json.dumps({"candidate": profile, "job": jd}, indent=2)[:14000],
    )
    try:
        data = generate_json(prompt, temperature=0.15)
        if not isinstance(data, dict):
            raise LlmError("Gap analysis did not return an object")
        gaps = {
            "matched_skills": _as_str_list(data.get("matched_skills")),
            "missing_skills": _as_str_list(data.get("missing_skills")),
            "weak_matches": _as_str_list(data.get("weak_matches")),
            "strong_matches": _as_str_list(data.get("strong_matches")),
            "experience_gaps": _as_str_list(data.get("experience_gaps")),
            "recommended_focus": _as_str_list(data.get("recommended_focus")),
            "notes": _as_str_list(data.get("notes")),
        }
    except LlmError as exc:
        gaps = _heuristic_gaps(profile, jd)
        gaps["notes"] = [f"LLM gap analysis failed; used heuristic fallback: {exc}"]

    write_json(GAP_JSON, gaps)
    return {"gap_analysis": gaps}


def _heuristic_gaps(profile: dict[str, Any], jd: dict[str, Any]) -> dict[str, Any]:
    resume_skills = {s.lower() for s in (profile.get("skills") or [])}
    required = list(jd.get("required_skills") or [])
    matched = [s for s in required if s.lower() in resume_skills or any(s.lower() in r for r in resume_skills)]
    missing = [s for s in required if s not in matched]
    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "weak_matches": [],
        "strong_matches": matched,
        "experience_gaps": [],
        "recommended_focus": missing[:4] or required[:3],
        "notes": ["Heuristic comparison of JD required skills against resume skill list."],
    }


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]
