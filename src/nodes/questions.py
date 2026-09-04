from __future__ import annotations

from typing import Any

from agents.question_planner import plan_questions


def generate_question_plan(state: dict[str, Any]) -> dict[str, Any]:
    attempt = int(state.get("generation_attempt") or 0) + 1
    questions = plan_questions(
        profile=state.get("candidate_profile") or {},
        jd=state.get("jd") or {},
        gaps=state.get("gap_analysis") or {},
        github=state.get("github") or {},
        attempt=attempt,
    )
    return {
        "questions": questions,
        "generation_attempt": attempt,
        "approval_status": "pending",
    }
