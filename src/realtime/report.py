"""Deterministic recruiter report from plan + transcript + evaluation.

Does not join LiveKit, scrape GitHub, or recompute the evaluator recommendation.
"""

from __future__ import annotations

from typing import Any

from prep.samples import SAMPLE_WARNING

DIMENSIONS = (
    "jd_resume_fit",
    "technical_competence",
    "problem_solving",
    "communication",
    "project_understanding",
    "github_credibility",
    "overall_interview",
)

REAL_DATA_LABEL = "REAL CANDIDATE DATA"
SAMPLE_DATA_LABEL = SAMPLE_WARNING


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        turns = payload.get("turns") or payload.get("transcript")
        if isinstance(turns, list):
            return [item for item in turns if isinstance(item, dict)]
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _questions_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in plan.get("questions") or []:
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = item
    return out


def _eval_by_question(evaluation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in evaluation.get("question_results") or []:
        if isinstance(item, dict) and item.get("question_id"):
            out[str(item["question_id"])] = item
    return out


def _qid(turn: dict[str, Any]) -> str:
    return _text(turn.get("question_id"))


def _attempted_ids(transcript: list[dict[str, Any]]) -> list[str]:
    asked: list[str] = []
    for turn in transcript:
        qid = _qid(turn)
        if qid and qid not in asked:
            asked.append(qid)
    return asked


def _transcript_stats(
    transcript: list[dict[str, Any]],
    questions_total: int,
) -> dict[str, Any]:
    interviewer = [t for t in transcript if t.get("speaker") == "interviewer"]
    candidate = [t for t in transcript if t.get("speaker") == "candidate"]
    follow_ups = [
        t
        for t in transcript
        if t.get("speaker") == "interviewer" and t.get("turn_type") == "follow_up"
    ]
    attempted = _attempted_ids(transcript)
    stamps = [t.get("timestamp") for t in transcript if isinstance(t.get("timestamp"), (int, float))]
    elapsed = None
    if len(stamps) >= 2:
        elapsed = int(round(max(stamps) - min(stamps)))
    return {
        "completed_turns": len(transcript),
        "interviewer_turns": len(interviewer),
        "candidate_turns": len(candidate),
        "questions_attempted": len(attempted),
        "questions_total": questions_total,
        "follow_ups": len(follow_ups),
        "elapsed_seconds": elapsed,
    }


def _follow_up_count(transcript: list[dict[str, Any]], question_id: str) -> int:
    return sum(
        1
        for turn in transcript
        if _qid(turn) == question_id
        and turn.get("speaker") == "interviewer"
        and turn.get("turn_type") == "follow_up"
    )


def _github_evidence(plan: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for question in plan.get("questions") or []:
        if not isinstance(question, dict):
            continue
        repository = _text(question.get("repository"))
        file_path = _text(question.get("file"))
        commit = _text(question.get("commit"))
        source = _text(question.get("source") or question.get("source_type")).lower()
        if not (repository or file_path or commit):
            continue
        if source != "github" and not (file_path and commit):
            continue
        key = (repository, file_path, commit, _text(question.get("id")))
        if key in seen:
            continue
        seen.add(key)
        claim = _text(question.get("source_reference")) or _text(question.get("evidence"))
        items.append(
            {
                "repository": repository,
                "file": file_path,
                "commit": commit,
                "related_question": _text(question.get("id")),
                "evidence": claim[:500],
            }
        )
    return items


def _scorecard(evaluation: dict[str, Any]) -> dict[str, int]:
    dims = evaluation.get("dimensions") or {}
    out: dict[str, int] = {}
    for name in DIMENSIONS:
        value = dims.get(name, 0)
        try:
            out[name] = int(value)
        except (TypeError, ValueError):
            out[name] = 0
    return out


def _interview_status(attempted: int, total: int) -> str:
    if total > 0 and attempted >= total:
        return "completed"
    return "partial"


def _limitations(
    *,
    status: str,
    attempted: int,
    total: int,
    sample_mode: bool,
    technical: int,
) -> list[str]:
    lines: list[str] = []
    if status == "partial":
        lines.append(
            f"Interview was partial; {attempted} of {total} approved questions were attempted."
        )
        lines.append(
            "Technical score may be affected by limited answered questions."
        )
        lines.append(
            "Recommendation should be interpreted in context of interview completeness."
        )
    elif technical < 60:
        lines.append(
            "Technical score may be affected by limited answered questions."
        )
    if sample_mode:
        lines.append(SAMPLE_DATA_LABEL)
    if not lines:
        lines.append("Scores and recommendation are copied from the evaluator; they were not recomputed.")
    return lines


def _interview_summary(
    name: str,
    role: str,
    company: str,
    status: str,
    attempted: int,
    total: int,
    follow_ups: int,
    recommendation: str,
    overall: int,
    data_label: str,
) -> str:
    status_word = "Partial" if status == "partial" else "Completed"
    who = name or "the candidate"
    where = f" for {role}" if role else ""
    if company:
        where += f" at {company}"
    return (
        f"{status_word} interview of {who}{where}. "
        f"{attempted} of {total} approved questions were attempted "
        f"({follow_ups} follow-ups). "
        f"Evaluator recommendation is {recommendation} with overall score {overall}. "
        f"{data_label}."
    )


def _question_results(
    plan: dict[str, Any],
    transcript: list[dict[str, Any]],
    evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
    attempted = set(_attempted_ids(transcript))
    eval_map = _eval_by_question(evaluation)
    results: list[dict[str, Any]] = []
    for question in plan.get("questions") or []:
        if not isinstance(question, dict) or not question.get("id"):
            continue
        qid = str(question["id"])
        if qid not in attempted:
            results.append(
                {
                    "question_id": qid,
                    "category": _text(question.get("category")),
                    "question": _text(question.get("question") or question.get("text")),
                    "status": "not_attempted",
                    "assessment": "",
                    "score": None,
                    "summary": "",
                    "follow_up_count": 0,
                    "evidence": [],
                    "concerns": [],
                }
            )
            continue
        ev = eval_map.get(qid) or {}
        results.append(
            {
                "question_id": qid,
                "category": _text(ev.get("category") or question.get("category")),
                "question": _text(question.get("question") or question.get("text")),
                "status": "attempted",
                "assessment": _text(ev.get("assessment")),
                "score": ev.get("score"),
                "summary": _text(ev.get("answer_summary")),
                "follow_up_count": _follow_up_count(transcript, qid),
                "evidence": list(ev.get("evidence") or []),
                "concerns": list(ev.get("concerns") or []),
            }
        )
    return results


def generate_report(
    plan: dict[str, Any],
    transcript: Any,
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Build a recruiter report. Does not call the evaluator or GitHub."""
    turns = _as_list(transcript)
    candidate = evaluation.get("candidate") or {}
    plan_candidate = plan.get("candidate") or {}
    plan_job = plan.get("job") or {}
    name = _text(candidate.get("name") or plan_candidate.get("name"))
    role = _text(candidate.get("role") or plan_job.get("role"))
    company = _text(candidate.get("company") or plan_job.get("company"))
    questions = [q for q in (plan.get("questions") or []) if isinstance(q, dict) and q.get("id")]
    stats = _transcript_stats(turns, len(questions))
    status = _interview_status(int(stats["questions_attempted"]), int(stats["questions_total"]))
    sample_mode = bool(plan.get("sample_mode"))
    data_label = SAMPLE_DATA_LABEL if sample_mode else REAL_DATA_LABEL
    recommendation = _text(evaluation.get("recommendation"))
    overall = int(evaluation.get("overall_score") or 0)
    scorecard = _scorecard(evaluation)
    reason = _text(evaluation.get("recommendation_reason"))
    return {
        "candidate": {
            "name": name,
            "role": role,
            "company": company,
        },
        "decision": {
            "recommendation": recommendation,
            "overall_score": overall,
            "reason": reason,
        },
        "scorecard": scorecard,
        "interview_summary": _interview_summary(
            name,
            role,
            company,
            status,
            int(stats["questions_attempted"]),
            int(stats["questions_total"]),
            int(stats["follow_ups"]),
            recommendation,
            overall,
            data_label,
        ),
        "strengths": list(evaluation.get("strengths") or []),
        "weaknesses": list(evaluation.get("weaknesses") or []),
        "concerns": list(evaluation.get("concerns") or []),
        "github_evidence": _github_evidence(plan),
        "question_results": _question_results(plan, turns, evaluation),
        "transcript_stats": stats,
        "interview_status": status,
        "questions_attempted": int(stats["questions_attempted"]),
        "questions_total": int(stats["questions_total"]),
        "limitations": _limitations(
            status=status,
            attempted=int(stats["questions_attempted"]),
            total=int(stats["questions_total"]),
            sample_mode=sample_mode,
            technical=int(scorecard.get("technical_competence") or 0),
        ),
        "metadata": {
            "plan_approved": _text(plan.get("approval_status")) == "approved"
            or bool(plan.get("approved_by_human")),
            "sample_mode": sample_mode,
            "data_label": data_label,
        },
    }


def _md_list(items: list[Any], empty: str = "None recorded.") -> str:
    values = [_text(item) for item in items if _text(item)]
    if not values:
        return empty
    return "\n".join(f"- {item}" for item in values)


def render_markdown(report: dict[str, Any]) -> str:
    candidate = report.get("candidate") or {}
    decision = report.get("decision") or {}
    scorecard = report.get("scorecard") or {}
    metadata = report.get("metadata") or {}
    stats = report.get("transcript_stats") or {}
    labels = {
        "jd_resume_fit": "JD / Resume Fit",
        "technical_competence": "Technical Competence",
        "problem_solving": "Problem Solving",
        "communication": "Communication",
        "project_understanding": "Project Understanding",
        "github_credibility": "GitHub Credibility",
        "overall_interview": "Overall Interview",
    }
    score_rows = "\n".join(
        f"| {labels[name]} | {scorecard.get(name, '')} |" for name in DIMENSIONS
    )
    github_lines: list[str] = []
    for item in report.get("github_evidence") or []:
        if not isinstance(item, dict):
            continue
        github_lines.append(
            f"- `{item.get('repository') or ''}` / `{item.get('file') or ''}` "
            f"@ `{item.get('commit') or ''}` "
            f"(question {item.get('related_question') or ''}) "
            f"— {item.get('evidence') or ''}"
        )
    q_blocks: list[str] = []
    for item in report.get("question_results") or []:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id") or ""
        status = item.get("status") or ""
        if status == "not_attempted":
            q_blocks.append(
                f"### {qid} — not attempted\n\n"
                f"**Category:** {item.get('category') or ''}\n\n"
                f"**Question:** {item.get('question') or ''}\n"
            )
            continue
        q_blocks.append(
            f"### {qid} — attempted\n\n"
            f"**Category:** {item.get('category') or ''}\n\n"
            f"**Question:** {item.get('question') or ''}\n\n"
            f"**Assessment:** {item.get('assessment') or ''}  \n"
            f"**Score:** {item.get('score')}  \n"
            f"**Follow-ups:** {item.get('follow_up_count')}\n\n"
            f"**Summary:** {item.get('summary') or ''}\n\n"
            f"**Evidence**\n{_md_list(item.get('evidence') or [])}\n\n"
            f"**Concerns**\n{_md_list(item.get('concerns') or [])}\n"
        )
    elapsed = stats.get("elapsed_seconds")
    elapsed_line = f"- Elapsed (from transcript timestamps): {elapsed}s" if elapsed is not None else "- Elapsed: not available"
    status = _text(report.get("interview_status")).upper() or "UNKNOWN"
    data_label = _text(metadata.get("data_label"))
    return f"""# Candidate Interview Report

**{data_label}**

## Candidate
Name: {candidate.get('name') or ''}
Role: {candidate.get('role') or ''}
Company: {candidate.get('company') or ''}

## Final Recommendation

{decision.get('recommendation') or ''}

Overall score: {decision.get('overall_score')}

Reason:
{decision.get('reason') or ''}

## Scorecard

| Dimension | Score |
|---|---:|
{score_rows}

## Interview Summary

{report.get('interview_summary') or ''}

## Strengths

{_md_list(report.get('strengths') or [])}

## Weaknesses

{_md_list(report.get('weaknesses') or [])}

## Concerns

{_md_list(report.get('concerns') or [])}

## GitHub Evidence

{chr(10).join(github_lines) if github_lines else 'None recorded from the approved plan.'}

## Question-by-Question Results

{chr(10).join(q_blocks)}

## Interview Status

- Status: **{status}**
- Questions attempted: {report.get('questions_attempted')} / {report.get('questions_total')}
- Completed turns: {stats.get('completed_turns')}
- Interviewer turns: {stats.get('interviewer_turns')}
- Candidate turns: {stats.get('candidate_turns')}
- Follow-ups: {stats.get('follow_ups')}
{elapsed_line}
- Plan approved: {metadata.get('plan_approved')}
- sample_mode: {metadata.get('sample_mode')}

## Limitations

{_md_list(report.get('limitations') or [])}
"""
