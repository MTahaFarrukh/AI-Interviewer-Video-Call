"""Run the five PDF persona transcripts through the existing evaluator + scorecard adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import QUESTION_PLAN_PATH
from plan_loader import load_approved_plan
from prep.io import read_json
from realtime.evaluate_interview import evaluate_interview
from realtime.scorecard import build_scorecard

PERSONAS = ("strong", "average", "weak", "bluffer", "nervous")
PERSONA_DIR = Path(__file__).resolve().parent / "personas"
RESULTS_PATH = Path(__file__).resolve().parent / "results.md"


def _turns_from_persona(plan: dict, persona: dict) -> list[dict]:
    answers = persona.get("answers") or {}
    turns: list[dict] = []
    for question in plan.get("questions") or []:
        if not isinstance(question, dict):
            continue
        qid = str(question.get("id") or "").strip()
        if not qid:
            continue
        turns.append(
            {
                "speaker": "interviewer",
                "text": str(question.get("question") or ""),
                "timestamp": len(turns) * 10.0,
                "question_id": qid,
                "turn_type": "question",
            }
        )
        answer = str(answers.get(qid) or "").strip()
        if answer:
            turns.append(
                {
                    "speaker": "candidate",
                    "text": answer,
                    "timestamp": len(turns) * 10.0 + 5.0,
                    "question_id": qid,
                    "turn_type": "answer",
                }
            )
    return turns


def run_persona(plan: dict, name: str) -> dict:
    path = PERSONA_DIR / f"{name}.json"
    persona = read_json(path)
    turns = _turns_from_persona(plan, persona)
    evaluation = evaluate_interview(plan, turns)
    scorecard = build_scorecard(
        plan,
        turns,
        evaluation,
        interview_date="2026-08-14",
        interview_id=f"eval-{name}",
    )
    expected = persona.get("expected") or {}
    return {
        "persona": name,
        "expected": expected,
        "legacy_score": evaluation.get("overall_score"),
        "legacy_recommendation": evaluation.get("recommendation"),
        "score": scorecard.get("overall_score"),
        "recommendation": scorecard.get("recommendation"),
        "confidence": scorecard.get("mean_confidence"),
        "interview_status": scorecard.get("interview_status"),
        "github_grounded_questions_asked": scorecard.get("github_grounded_questions_asked"),
        "guardrail_flags": scorecard.get("guardrail_flags") or [],
        "strengths": scorecard.get("strengths") or [],
        "concerns": scorecard.get("concerns") or [],
        "competencies": scorecard.get("competencies") or [],
        "turns": len(turns),
    }


def rank_rows(rows: list[dict]) -> list[dict]:
    ordered = sorted(rows, key=lambda item: (-float(item.get("score") or 0), item["persona"]))
    for index, row in enumerate(ordered, start=1):
        row["ranking"] = index
    by_name = {row["persona"]: row for row in ordered}
    for row in rows:
        row["ranking"] = by_name[row["persona"]]["ranking"]
    return rows


def _check_expectations(rows: list[dict]) -> list[str]:
    by_name = {row["persona"]: row for row in rows}
    failures: list[str] = []
    strong = float(by_name["strong"]["score"] or 0)
    average = float(by_name["average"]["score"] or 0)
    weak = float(by_name["weak"]["score"] or 0)
    bluffer = float(by_name["bluffer"]["score"] or 0)
    nervous = float(by_name["nervous"]["score"] or 0)
    if not (strong > average > weak):
        failures.append(
            f"Expected Strong > Average > Weak, got {strong} / {average} / {weak}."
        )
    if not (bluffer < average):
        failures.append(f"Expected Bluffer < Average, got {bluffer} / {average}.")
    if abs(nervous - strong) > 1.5:
        failures.append(
            f"Expected Nervous near Strong (delta <= 1.5), got {nervous} vs {strong}."
        )
    return failures


def render_results(rows: list[dict], failures: list[str]) -> str:
    lines = [
        "# Persona eval results",
        "",
        "These transcripts are synthetic. They were scored with the existing offline evaluator,",
        "then mapped through the PDF scorecard adapter. Rankings were not hardcoded.",
        "",
        "| Persona | Score (1–5) | Legacy 0–100 | Recommendation | Confidence | Rank | Expected |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    for row in sorted(rows, key=lambda item: item.get("ranking") or 99):
        expected = row.get("expected") or {}
        lines.append(
            "| {persona} | {score} | {legacy} | {rec} | {conf} | {rank} | {exp} |".format(
                persona=row["persona"],
                score=row.get("score"),
                legacy=row.get("legacy_score"),
                rec=row.get("recommendation"),
                conf=row.get("confidence"),
                rank=row.get("ranking"),
                exp=expected.get("behavior") or expected.get("rank") or "",
            )
        )
    lines.extend(["", "## Actual vs expected", ""])
    for row in rows:
        expected = row.get("expected") or {}
        lines.append(f"### {row['persona']}")
        lines.append("")
        lines.append(f"- Expected rank/behavior: {expected.get('rank')} — {expected.get('behavior')}")
        lines.append(
            f"- Actual: score={row.get('score')} recommendation={row.get('recommendation')} "
            f"confidence={row.get('confidence')} rank={row.get('ranking')}"
        )
        lines.append(
            f"- Legacy evaluator: {row.get('legacy_score')} / {row.get('legacy_recommendation')}"
        )
        lines.append("")
    lines.extend(["## Failures / limitations", ""])
    if failures:
        for item in failures:
            lines.append(f"- {item}")
    else:
        lines.append("- Ranking checks passed for this synthetic set.")
    lines.extend(
        [
            "",
            "- Scorecard overall is the mean of evidence-gated 1–5 competency scores, not a raw 0–100 dump.",
            "- JD/resume fit is not scored from gap analysis alone; it needs a candidate quote.",
            "- These personas are not the live Taha interview.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    plan = load_approved_plan(QUESTION_PLAN_PATH)
    if not plan:
        print("Approved plan missing", file=sys.stderr)
        return 1
    rows = [run_persona(plan, name) for name in PERSONAS]
    rank_rows(rows)
    failures = _check_expectations(rows)
    RESULTS_PATH.write_text(render_results(rows, failures), encoding="utf-8")
    print(json.dumps({"results": str(RESULTS_PATH), "failures": failures, "rows": [
        {
            "persona": row["persona"],
            "score": row["score"],
            "recommendation": row["recommendation"],
            "ranking": row["ranking"],
        }
        for row in rows
    ]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
