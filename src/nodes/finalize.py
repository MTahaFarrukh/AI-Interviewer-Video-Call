from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import QUESTION_PLAN_PATH
from prep.io import write_json
from prep.paths import PREP_QUESTION_PLAN
from prep.samples import SAMPLE_WARNING, is_sample_github


def finalize_plan(state: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    plan = {
        "candidate": state.get("candidate_profile") or {},
        "job": {k: v for k, v in (state.get("jd") or {}).items() if k != "raw_text"},
        "gap_analysis": state.get("gap_analysis") or {},
        "github_projects": (state.get("github") or {}).get("projects") or state.get("github_projects") or [],
        "github": {
            "username": (state.get("github") or {}).get("username") or state.get("github_username") or "",
            "url": (state.get("github") or {}).get("url") or state.get("github_url") or "",
            "error": (state.get("github") or {}).get("error") or state.get("github_error") or "",
            "repos_considered": (state.get("github") or {}).get("repos_considered") or 0,
        },
        "questions": state.get("questions") or [],
        "approval_status": state.get("approval_status") or "approved",
        "approved_by_human": state.get("approval_status") in {"approved", "edited"},
        "edits_made": state.get("edits_made") or [],
        "validation": state.get("validation") or {},
        "thread_id": state.get("thread_id") or "",
        "timestamp": now,
        "session_id": state.get("thread_id") or "",
        "sample_mode": bool(
            state.get("sample_mode")
            or is_sample_github((state.get("github") or {}).get("username") or "")
        ),
    }
    if plan["sample_mode"]:
        plan["warning"] = SAMPLE_WARNING
    write_json(QUESTION_PLAN_PATH, plan)
    write_json(PREP_QUESTION_PLAN, plan)
    return {
        "final_plan": plan,
        "finalized": True,
        "output_path": str(QUESTION_PLAN_PATH),
    }
