from __future__ import annotations

from typing import Any

from langgraph.types import interrupt


def recruiter_review(state: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "type": "recruiter_review",
        "candidate": (state.get("candidate_profile") or {}).get("name") or "",
        "role": (state.get("jd") or {}).get("role") or "",
        "validation": state.get("validation") or {},
        "questions": [
            {
                "id": q.get("id"),
                "category": q.get("category"),
                "question": q.get("question") or q.get("text"),
                "source_reference": q.get("source_reference"),
            }
            for q in (state.get("questions") or [])
        ],
    }
    decision = interrupt(payload)
    if not isinstance(decision, dict):
        decision = {"action": str(decision or "").strip().lower()}

    action = str(decision.get("action") or "").strip().lower()
    if action not in {"approve", "edit", "reject"}:
        return {
            "recruiter_action": "invalid",
            "approval_status": "pending",
            "warnings": ["Unknown recruiter action; expected approve, edit, or reject."],
        }

    questions = list(state.get("questions") or [])
    if action == "edit":
        questions, edits_made = _apply_edits(questions, decision.get("edits") or [])
        return {
            "questions": questions,
            "recruiter_action": action,
            "approval_status": "edited",
            "edits_made": edits_made,
        }
    if action == "reject":
        return {
            "recruiter_action": action,
            "approval_status": "rejected",
            "edits_made": [{"action": "reject", "reason": str(decision.get("reason") or "")}],
        }
    return {
        "recruiter_action": action,
        "approval_status": "approved",
        "edits_made": [],
    }


def _apply_edits(
    questions: list[dict[str, Any]],
    edits: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(edits, list):
        return questions, []
    by_id = {str(q.get("id")): q for q in questions}
    applied: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        qid = str(edit.get("id") or "").strip()
        new_text = str(edit.get("question") or edit.get("text") or "").strip()
        if qid not in by_id or not new_text:
            continue
        old = str(by_id[qid].get("question") or "")
        by_id[qid]["question"] = new_text
        by_id[qid]["text"] = new_text
        applied.append({"id": qid, "before": old, "after": new_text})
    return list(by_id.values()) if applied else questions, applied
