"""Read-only recruiter MCP server (FastMCP stdio).

Not on the LiveKit / Gemini Live audio path. Does not start interviews,
mutate plans, or expose API keys.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastmcp import FastMCP

from config import (
    INTERVIEW_STORE_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    PDF_SCORECARD_PATH,
    QUESTION_PLAN_PATH,
)
from plan_loader import load_approved_plan
from prep.io import read_json
from prep.paths import GAP_JSON, PROFILE_JSON
from realtime.evaluate_interview import evaluate_interview
from realtime.report import generate_report
from realtime.scorecard import validate_scorecard
from realtime.store import InterviewStore

TOOL_NAMES = (
    "get_interview_status",
    "get_interview_transcript",
    "get_current_question",
    "get_interview_report",
    "list_interviews",
    "get_question_plan",
    "get_github_evidence",
)

_SECRET_ENV_NAMES = (
    "GOOGLE_API_KEY",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "GITHUB_TOKEN",
)
_SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apisecret",
    "api_secret",
    "secret",
    "password",
    "token",
    "authorization",
)

_paths: dict[str, Path] = {
    "store": INTERVIEW_STORE_PATH,
    "plan": QUESTION_PLAN_PATH,
    "scorecard": PDF_SCORECARD_PATH,
    "transcript": INTERVIEW_TRANSCRIPT_PATH,
}

mcp = FastMCP(
    "firstround",
    instructions=(
        "Read-only recruiter tools for FirstRound interviews. "
        "Inspect persisted interview state, the approved question plan, "
        "and offline reports. Do not start or control the live interview."
    ),
)


def configure(
    *,
    store_path: Path | None = None,
    plan_path: Path | None = None,
    scorecard_path: Path | None = None,
    transcript_path: Path | None = None,
) -> None:
    """Test hook: point tools at fixed application paths. Clients cannot set these."""
    if store_path is not None:
        _paths["store"] = Path(store_path)
    else:
        _paths["store"] = INTERVIEW_STORE_PATH
    if plan_path is not None:
        _paths["plan"] = Path(plan_path)
    else:
        _paths["plan"] = QUESTION_PLAN_PATH
    if scorecard_path is not None:
        _paths["scorecard"] = Path(scorecard_path)
    else:
        _paths["scorecard"] = PDF_SCORECARD_PATH
    if transcript_path is not None:
        _paths["transcript"] = Path(transcript_path)
    else:
        _paths["transcript"] = INTERVIEW_TRANSCRIPT_PATH


def _store() -> InterviewStore:
    return InterviewStore(_paths["store"])


def _plan() -> dict[str, Any] | None:
    return load_approved_plan(_paths["plan"])


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error": code, "message": message}
    payload.update(extra)
    return _sanitize(payload)


def _ok(**payload: Any) -> dict[str, Any]:
    data = {"ok": True, **payload}
    return _sanitize(data)


def _secret_values() -> list[str]:
    values: list[str] = []
    for name in _SECRET_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if len(value) >= 8:
            values.append(value)
    return values


def _is_secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS)


def _redact_text(value: str) -> str:
    cleaned = value
    for secret in _secret_values():
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                continue
            out[str(key)] = _sanitize(item)
        return out
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _public_turn(turn: dict[str, Any]) -> dict[str, Any]:
    return {
        "speaker": str(turn.get("speaker") or ""),
        "question_id": str(turn.get("question_id") or ""),
        "turn_type": str(turn.get("turn_type") or ""),
        "text": str(turn.get("text") or ""),
        "timestamp": turn.get("timestamp"),
    }


def _question_by_id(plan: dict[str, Any], question_id: str) -> dict[str, Any] | None:
    wanted = (question_id or "").strip()
    if not wanted:
        return None
    for item in plan.get("questions") or []:
        if isinstance(item, dict) and str(item.get("id") or "").strip() == wanted:
            return item
    return None


def _is_github_question(question: dict[str, Any]) -> bool:
    source = str(question.get("source") or question.get("source_type") or "").strip().lower()
    if source == "github":
        return True
    return bool(
        question.get("repository")
        and (question.get("file") or question.get("commit") or question.get("source_reference"))
    )


def _load_optional(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = read_json(path)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _status_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "interview_id": record.get("interview_id") or "",
        "candidate": record.get("candidate") or "",
        "role": record.get("role") or "",
        "company": record.get("company") or "",
        "status": record.get("status") or "",
        "current_question_id": record.get("current_question_id") or "",
        "current_question_index": int(record.get("current_question_index") or 0),
        "follow_up_count": int(record.get("follow_up_count") or 0),
        "phase": record.get("phase") or "",
        "elapsed_seconds": float(record.get("elapsed_seconds") or 0),
        "completed_question_ids": list(record.get("completed_question_ids") or []),
        "started_at": record.get("started_at"),
        "last_updated_at": record.get("last_updated_at"),
    }


@mcp.tool
def get_interview_status(interview_id: str) -> dict[str, Any]:
    """Return persisted live-interview status. Read-only."""
    iid = (interview_id or "").strip()
    if not iid:
        return _error("invalid_interview_id", "interview_id is required")
    record = _store().get_interview(iid)
    if not record:
        return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
    return _ok(**_status_fields(record))


@mcp.tool
def get_interview_transcript(interview_id: str) -> dict[str, Any]:
    """Return completed transcript turns from SQLite. No audio."""
    iid = (interview_id or "").strip()
    if not iid:
        return _error("invalid_interview_id", "interview_id is required")
    store = _store()
    if not store.get_interview(iid):
        return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
    turns = [_public_turn(turn) for turn in store.get_transcript(iid)]
    return _ok(interview_id=iid, turns=turns)


@mcp.tool
def get_current_question(interview_id: str) -> dict[str, Any]:
    """Return only the currently active approved question. Does not leak later questions."""
    iid = (interview_id or "").strip()
    if not iid:
        return _error("invalid_interview_id", "interview_id is required")
    record = _store().get_interview(iid)
    if not record:
        return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
    plan = _plan()
    if not plan:
        return _error("plan_unavailable", "No approved question plan is available")
    qid = str(record.get("current_question_id") or "").strip()
    if not qid:
        return _error(
            "no_current_question",
            "No current question (interview may be in wrap-up).",
            interview_id=iid,
        )
    question = _question_by_id(plan, qid)
    if not question:
        return _error("question_not_found", f"Question not found: {qid}", question_id=qid)
    payload: dict[str, Any] = {
        "interview_id": iid,
        "question_id": qid,
        "category": str(question.get("category") or ""),
        "source": str(question.get("source") or question.get("source_type") or ""),
        "question": str(question.get("question") or question.get("text") or ""),
    }
    if question.get("source_reference"):
        payload["source_reference"] = str(question.get("source_reference") or "")
    return _ok(**payload)


@mcp.tool
def get_interview_report(interview_id: str) -> dict[str, Any]:
    """Build an offline report from a persisted transcript. Does not join LiveKit."""
    iid = (interview_id or "").strip()
    if not iid:
        return _error("invalid_interview_id", "interview_id is required")
    record = _store().get_interview(iid)
    if not record:
        return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
    transcript = [_public_turn(turn) for turn in (record.get("transcript") or [])]
    if not transcript:
        return _error(
            "report_not_available",
            "report not available: this interview has no completed transcript turns yet",
            interview_id=iid,
            available=False,
        )
    plan = _plan()
    if not plan:
        return _error("plan_unavailable", "No approved question plan is available")
    evaluation = evaluate_interview(
        plan,
        transcript,
        profile=_load_optional(PROFILE_JSON),
        gap=_load_optional(GAP_JSON) or plan.get("gap_analysis"),
    )
    report = generate_report(plan, transcript, evaluation)
    decision = report.get("decision") or {}
    return _ok(
        interview_id=iid,
        available=True,
        candidate=report.get("candidate") or {},
        decision=decision,
        recommendation=decision.get("recommendation"),
        overall_score=decision.get("overall_score"),
        scorecard=report.get("scorecard") or {},
        interview_status=report.get("interview_status"),
        strengths=report.get("strengths") or [],
        weaknesses=report.get("weaknesses") or [],
        concerns=report.get("concerns") or [],
        github_evidence=report.get("github_evidence") or [],
        sample_mode=(report.get("metadata") or {}).get("sample_mode"),
    )


@mcp.tool
def list_interviews(limit: int = 20) -> dict[str, Any]:
    """List recent persisted interviews, newest first."""
    interviews = _store().list_interviews(limit=limit)
    return _ok(interviews=interviews, count=len(interviews))


@mcp.tool
def get_question_plan() -> dict[str, Any]:
    """Safe recruiter summary of the currently approved question plan. No resume text."""
    plan = _plan()
    if not plan:
        return _error("plan_unavailable", "No approved question plan is available")
    candidate = plan.get("candidate") or {}
    job = plan.get("job") or {}
    questions = []
    for item in plan.get("questions") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        entry = {
            "id": str(item.get("id") or ""),
            "category": str(item.get("category") or ""),
            "source": str(item.get("source") or item.get("source_type") or ""),
        }
        if item.get("source_reference"):
            entry["source_reference"] = str(item.get("source_reference") or "")
        questions.append(entry)
    return _ok(
        candidate={
            "name": str(candidate.get("name") or ""),
            "github_url": str(candidate.get("github_url") or ""),
        },
        role=str(job.get("role") or ""),
        company=str(job.get("company") or ""),
        approval_status=str(plan.get("approval_status") or ""),
        sample_mode=bool(plan.get("sample_mode")),
        question_ids=[q["id"] for q in questions],
        questions=questions,
    )


@mcp.tool
def get_github_evidence(question_id: str) -> dict[str, Any]:
    """Return approved GitHub grounding for one question. No live GitHub API calls."""
    qid = (question_id or "").strip()
    if not qid:
        return _error("invalid_question_id", "question_id is required")
    plan = _plan()
    if not plan:
        return _error("plan_unavailable", "No approved question plan is available")
    question = _question_by_id(plan, qid)
    if not question:
        return _error("question_not_found", f"Question not found: {qid}", question_id=qid)
    if not _is_github_question(question):
        return _error(
            "not_github_question",
            f"{qid} is not a GitHub-sourced question",
            question_id=qid,
        )
    return _ok(
        question_id=qid,
        repository=str(question.get("repository") or ""),
        file=str(question.get("file") or ""),
        commit=str(question.get("commit") or ""),
        source_reference=str(question.get("source_reference") or ""),
        question=str(question.get("question") or question.get("text") or ""),
    )


def _load_turns(interview_id: str = "") -> list[dict[str, Any]]:
    iid = (interview_id or "").strip()
    if iid:
        record = _store().get_interview(iid)
        if record:
            turns = record.get("transcript") or []
            if isinstance(turns, list):
                return [item for item in turns if isinstance(item, dict)]
    path = _paths.get("transcript") or INTERVIEW_TRANSCRIPT_PATH
    if path.is_file():
        try:
            payload = read_json(path)
        except Exception:
            payload = []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            turns = payload.get("turns") or payload.get("transcript") or []
            if isinstance(turns, list):
                return [item for item in turns if isinstance(item, dict)]
    return []


@mcp.tool
def get_candidate(interview_id: str = "") -> dict[str, Any]:
    """Return candidate identity from the approved plan or a persisted interview."""
    iid = (interview_id or "").strip()
    if iid:
        record = _store().get_interview(iid)
        if not record:
            return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
        return _ok(
            interview_id=iid,
            name=str(record.get("candidate") or ""),
            role=str(record.get("role") or ""),
            company=str(record.get("company") or ""),
        )
    plan = _plan()
    if not plan:
        return _error("plan_unavailable", "No approved question plan is available")
    candidate = plan.get("candidate") or {}
    job = plan.get("job") or {}
    return _ok(
        name=str(candidate.get("name") or ""),
        github_url=str(candidate.get("github_url") or ""),
        role=str(job.get("role") or ""),
        company=str(job.get("company") or ""),
    )


@mcp.tool
def save_score(scorecard: dict, interview_id: str = "") -> dict[str, Any]:
    """Validate evidence quotes and persist output/scorecard.json. Does not mutate SQLite."""
    if not isinstance(scorecard, dict):
        return _error("invalid_scorecard", "scorecard must be an object")
    iid = (interview_id or str(scorecard.get("interview_id") or "")).strip()
    if iid:
        record = _store().get_interview(iid)
        if not record:
            return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
    turns = _load_turns(iid)
    prepared = validate_scorecard(scorecard, turns)
    if iid:
        prepared["interview_id"] = iid
    scored = [item for item in (prepared.get("competencies") or []) if item.get("score") is not None]
    invalid = [
        flag
        for flag in (prepared.get("guardrail_flags") or [])
        if isinstance(flag, dict) and flag.get("type") == "invalid_evidence_quote"
    ]
    target = Path(_paths["scorecard"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(prepared, indent=2, ensure_ascii=False), encoding="utf-8")
    return _ok(
        interview_id=iid or None,
        path=str(target),
        saved=True,
        scored_competencies=len(scored),
        rejected_quotes=len(invalid),
        recommendation=prepared.get("recommendation"),
        overall_score=prepared.get("overall_score"),
    )


@mcp.tool
def get_scorecard(interview_id: str = "") -> dict[str, Any]:
    """Return the current PDF scorecard artifact."""
    iid = (interview_id or "").strip()
    if iid:
        record = _store().get_interview(iid)
        if not record:
            return _error("interview_not_found", f"Interview not found: {iid}", interview_id=iid)
    path = Path(_paths["scorecard"])
    if not path.is_file():
        return _error("scorecard_not_found", "No scorecard has been saved yet", interview_id=iid or None)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _error("scorecard_unreadable", "Scorecard file could not be parsed")
    if not isinstance(payload, dict):
        return _error("scorecard_unreadable", "Scorecard file is not an object")
    stored_id = str(payload.get("interview_id") or "").strip()
    if iid and stored_id and stored_id != iid:
        return _error(
            "scorecard_mismatch",
            f"Saved scorecard belongs to {stored_id}, not {iid}",
            interview_id=iid,
        )
    return _ok(interview_id=iid or stored_id or None, scorecard=payload)


if __name__ == "__main__":
    mcp.run()
