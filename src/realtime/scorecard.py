"""PDF scorecard adapter over the existing evaluator. Does not rescore audio."""

from __future__ import annotations

from typing import Any

from realtime.evaluate_interview import evaluate_interview

RECOMMENDATION_MAP = {
    "GO": "hire",
    "NO_GO": "no_hire",
    "REVIEW": "borderline",
    "hire": "hire",
    "no_hire": "no_hire",
    "borderline": "borderline",
}

COMPETENCIES = (
    ("Technical competence", "technical_competence", ("Technical",)),
    ("Problem solving", "problem_solving", ("Scenario",)),
    ("Communication", "communication", ()),
    ("Project understanding", "project_understanding", ("Project/GitHub",)),
    ("GitHub credibility", "github_credibility", ("Project/GitHub",)),
    ("JD / resume fit", "jd_resume_fit", ()),
)

MIN_QUOTE_CHARS = 12


def normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def candidate_texts(transcript: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for turn in transcript:
        speaker = str(turn.get("speaker") or "").strip().lower()
        if speaker not in {"candidate"}:
            continue
        text = normalize_whitespace(str(turn.get("text") or ""))
        if text:
            texts.append(text)
    return texts


def quote_in_candidate_transcript(quote: str, transcript: list[dict[str, Any]]) -> bool:
    needle = normalize_whitespace(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    lowered = needle.lower()
    for text in candidate_texts(transcript):
        if lowered in text.lower():
            return True
    return False


def _best_quote(transcript: list[dict[str, Any]], question_ids: set[str] | None = None) -> str:
    best = ""
    for turn in transcript:
        speaker = str(turn.get("speaker") or "").strip().lower()
        if speaker != "candidate":
            continue
        qid = str(turn.get("question_id") or "").strip()
        if question_ids is not None and qid not in question_ids:
            continue
        text = normalize_whitespace(str(turn.get("text") or ""))
        if len(text) < MIN_QUOTE_CHARS:
            continue
        if len(text) > len(best):
            best = text
    return best


def _score_1_to_5(value_100: Any) -> int:
    try:
        number = float(value_100)
    except (TypeError, ValueError):
        return 1
    if number >= 81:
        return 5
    if number >= 61:
        return 4
    if number >= 41:
        return 3
    if number >= 21:
        return 2
    return 1


def _confidence(quote: str, attempted: int, total: int) -> float:
    if len(normalize_whitespace(quote)) < MIN_QUOTE_CHARS:
        return 0.0
    coverage = attempted / max(total, 1)
    quote_conf = min(1.0, len(normalize_whitespace(quote)) / 80.0)
    return round(max(0.0, min(1.0, 0.35 * coverage + 0.65 * quote_conf)), 2)


def _questions_by_category(plan: dict[str, Any], categories: tuple[str, ...]) -> set[str]:
    wanted = {item.lower() for item in categories}
    ids: set[str] = set()
    for question in plan.get("questions") or []:
        if not isinstance(question, dict):
            continue
        category = str(question.get("category") or "")
        source = str(question.get("source") or question.get("source_type") or "")
        qid = str(question.get("id") or "").strip()
        if not qid:
            continue
        if not wanted:
            ids.add(qid)
            continue
        if category in categories or source.lower() == "github" and "github" in " ".join(wanted).lower():
            ids.add(qid)
        elif any(token.lower() in category.lower() for token in wanted):
            ids.add(qid)
    return ids


def _github_question_ids(plan: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for question in plan.get("questions") or []:
        if not isinstance(question, dict):
            continue
        qid = str(question.get("id") or "").strip()
        source = str(question.get("source") or question.get("source_type") or "").lower()
        category = str(question.get("category") or "").lower()
        if qid and (source == "github" or "github" in category or question.get("file")):
            ids.add(qid)
    return ids


def _attempted_ids(transcript: list[dict[str, Any]]) -> list[str]:
    asked: list[str] = []
    for turn in transcript:
        qid = str(turn.get("question_id") or "").strip()
        if qid and qid not in asked:
            asked.append(qid)
    return asked


def _duration_seconds(transcript: list[dict[str, Any]]) -> int:
    stamps: list[float] = []
    for turn in transcript:
        raw = turn.get("timestamp")
        if isinstance(raw, (int, float)):
            stamps.append(float(raw))
        raw_ms = turn.get("timestamp_ms")
        if isinstance(raw_ms, (int, float)) and not stamps:
            stamps.append(float(raw_ms) / 1000.0)
    if len(stamps) < 2:
        return 0
    first, last = min(stamps), max(stamps)
    if last > 1_000_000_000_000:
        return int(round((last - first) / 1000.0))
    return max(0, int(round(last - first)))


def apply_evidence_guardrail(
    competencies: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    flags: list[dict[str, Any]] = []
    cleaned: list[dict[str, Any]] = []
    for item in competencies:
        row = dict(item)
        quote = str(row.get("evidence_quote") or "")
        score = row.get("score")
        if score is None:
            cleaned.append(row)
            continue
        if quote_in_candidate_transcript(quote, transcript):
            cleaned.append(row)
            continue
        flags.append(
            {
                "type": "invalid_evidence_quote",
                "competency": row.get("name"),
                "reason": "Score rejected because the evidence quote is missing, too short, or not in a candidate turn.",
            }
        )
        row["score"] = None
        row["confidence"] = 0.0
        row["evidence_quote"] = ""
        row["reasoning"] = "Insufficient candidate-transcript evidence to score this competency."
        cleaned.append(row)
    return cleaned, flags


def build_scorecard(
    plan: dict[str, Any],
    transcript: list[dict[str, Any]],
    evaluation: dict[str, Any] | None = None,
    *,
    interview_date: str = "",
    interview_id: str = "",
) -> dict[str, Any]:
    eval_payload = evaluation or evaluate_interview(plan, transcript)
    dimensions = eval_payload.get("dimensions") or {}
    attempted = _attempted_ids(transcript)
    total = len([q for q in (plan.get("questions") or []) if isinstance(q, dict)])
    github_ids = _github_question_ids(plan)
    github_asked = len([qid for qid in attempted if qid in github_ids])
    competencies: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []

    for name, dim_key, categories in COMPETENCIES:
        qids = _questions_by_category(plan, categories) if categories else None
        if dim_key == "github_credibility":
            qids = github_ids
        if dim_key == "jd_resume_fit":
            qids = set()
        quote = _best_quote(transcript, qids)
        if dim_key == "communication" and not quote:
            quote = _best_quote(transcript, None)
        valid = quote_in_candidate_transcript(quote, transcript)
        mapped = _score_1_to_5(dimensions.get(dim_key))
        if not valid:
            flags.append(
                {
                    "type": "insufficient_evidence",
                    "competency": name,
                    "reason": "No valid candidate-transcript quote of at least 12 characters.",
                }
            )
            competencies.append(
                {
                    "name": name,
                    "score": None,
                    "confidence": 0.0,
                    "evidence_quote": "",
                    "reasoning": "Not scored: the transcript does not contain a usable candidate quote for this competency.",
                }
            )
            continue
        reasoning = str(eval_payload.get("recommendation_reason") or "").strip()
        if dim_key == "jd_resume_fit":
            reasoning = (
                "Mapped from the existing JD/resume-fit dimension only because a candidate quote exists; "
                "gap-analysis matches are not used as transcript evidence."
            )
        competencies.append(
            {
                "name": name,
                "score": mapped,
                "confidence": _confidence(quote, len(attempted), total or 12),
                "evidence_quote": quote,
                "reasoning": reasoning or f"Mapped from existing {dim_key} using transcript evidence.",
            }
        )

    competencies, extra_flags = apply_evidence_guardrail(competencies, transcript)
    flags.extend(extra_flags)
    scored = [item["score"] for item in competencies if isinstance(item.get("score"), int)]
    overall = round(sum(scored) / len(scored), 2) if scored else 0.0
    rec_raw = str(eval_payload.get("recommendation") or "")
    recommendation = RECOMMENDATION_MAP.get(rec_raw, "no_hire")
    if not scored:
        recommendation = "no_hire"
    if len(attempted) < (total or 12):
        flags.append(
            {
                "type": "partial_interview",
                "reason": f"Only {len(attempted)} of {total or 12} approved questions were attempted.",
            }
        )
    candidate = plan.get("candidate") or {}
    job = plan.get("job") or {}
    eval_candidate = eval_payload.get("candidate") or {}
    strengths = [str(item) for item in (eval_payload.get("strengths") or []) if str(item).strip()]
    concerns = [str(item) for item in (eval_payload.get("concerns") or []) if str(item).strip()]
    concerns.extend(str(item) for item in (eval_payload.get("weaknesses") or []) if str(item).strip())
    rec_reason = str(eval_payload.get("recommendation_reason") or "").strip()
    if not scored:
        rec_reason = "No competency could be scored from a valid candidate-transcript quote."
    mean_conf = 0.0
    confs = [float(item.get("confidence") or 0) for item in competencies if item.get("score") is not None]
    if confs:
        mean_conf = round(sum(confs) / len(confs), 2)
    return {
        "candidate_name": str(eval_candidate.get("name") or candidate.get("name") or "").strip(),
        "role": str(eval_candidate.get("role") or job.get("role") or "").strip(),
        "interview_date": interview_date,
        "duration_seconds": _duration_seconds(transcript),
        "competencies": competencies,
        "overall_score": overall,
        "recommendation": recommendation,
        "recommendation_reasoning": rec_reason,
        "strengths": strengths,
        "concerns": concerns,
        "guardrail_flags": flags,
        "github_grounded_questions_asked": github_asked,
        "interview_id": interview_id,
        "interview_status": "partial" if len(attempted) < (total or 12) else "completed",
        "legacy_recommendation": rec_raw,
        "legacy_overall_score_100": eval_payload.get("overall_score"),
        "mean_confidence": mean_conf,
        "questions_attempted": len(attempted),
        "questions_total": total or 12,
        "sample_mode": bool(plan.get("sample_mode")),
    }


def validate_scorecard(
    scorecard: dict[str, Any],
    transcript: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = dict(scorecard)
    competencies, flags = apply_evidence_guardrail(list(payload.get("competencies") or []), transcript)
    payload["competencies"] = competencies
    existing = [item for item in (payload.get("guardrail_flags") or []) if isinstance(item, dict)]
    payload["guardrail_flags"] = existing + flags
    scored = [item["score"] for item in competencies if isinstance(item.get("score"), int)]
    payload["overall_score"] = round(sum(scored) / len(scored), 2) if scored else 0.0
    rec = str(payload.get("recommendation") or "no_hire")
    if rec not in {"hire", "no_hire", "borderline"}:
        payload["recommendation"] = RECOMMENDATION_MAP.get(rec, "no_hire")
    if not scored:
        payload["recommendation"] = "no_hire"
        payload["recommendation_reasoning"] = (
            payload.get("recommendation_reasoning")
            or "No competency could be scored from a valid candidate-transcript quote."
        )
    return payload
