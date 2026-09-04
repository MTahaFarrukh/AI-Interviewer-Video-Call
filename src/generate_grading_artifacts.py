"""Write PDF-required grading artifacts from the existing Taha interview data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    INTERVIEW_EVALUATION_PATH,
    INTERVIEW_STORE_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    PDF_REPORT_PATH,
    PDF_SCORECARD_PATH,
    PDF_TRANSCRIPT_PATH,
    QUESTION_PLAN_PATH,
)
from plan_loader import load_approved_plan
from prep.io import read_json, write_json
from realtime.evaluate_interview import evaluate_interview
from realtime.pdf_report import write_report_pdf
from realtime.scorecard import build_scorecard
from realtime.store import InterviewStore
from realtime.transcript_export import export_transcript

REAL_INTERVIEW_ID = "AJ_mPYT3PkhgjPw"
INTERVIEW_DATE = "2026-08-14"


def _load_real_turns() -> list[dict]:
    if INTERVIEW_STORE_PATH.is_file():
        store = InterviewStore(INTERVIEW_STORE_PATH)
        turns = store.get_transcript(REAL_INTERVIEW_ID)
        if len(turns) >= 2:
            return turns
    if INTERVIEW_TRANSCRIPT_PATH.is_file():
        payload = read_json(INTERVIEW_TRANSCRIPT_PATH)
        if isinstance(payload, list) and len(payload) >= 2:
            return payload
    raise SystemExit(
        f"No transcript with candidate turns for {REAL_INTERVIEW_ID}."
    )


def main() -> int:
    plan = load_approved_plan(QUESTION_PLAN_PATH)
    if not plan:
        raise SystemExit("Approved question plan is missing.")
    turns = _load_real_turns()
    INTERVIEW_TRANSCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(INTERVIEW_TRANSCRIPT_PATH, turns)

    exported = export_transcript(turns)
    PDF_TRANSCRIPT_PATH.write_text(
        json.dumps(exported, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Always re-score this interview; do not reuse a prior evaluation file.
    evaluation = evaluate_interview(plan, turns)
    write_json(INTERVIEW_EVALUATION_PATH, evaluation)
    scorecard = build_scorecard(
        plan,
        turns,
        evaluation,
        interview_date=INTERVIEW_DATE,
        interview_id=REAL_INTERVIEW_ID,
    )
    PDF_SCORECARD_PATH.write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_report_pdf(scorecard, PDF_REPORT_PATH)
    print(
        json.dumps(
            {
                "interview_id": REAL_INTERVIEW_ID,
                "transcript": str(PDF_TRANSCRIPT_PATH),
                "scorecard": str(PDF_SCORECARD_PATH),
                "pdf": str(PDF_REPORT_PATH),
                "turns": len(exported.get("turns") or []),
                "recommendation": scorecard.get("recommendation"),
                "overall_score": scorecard.get("overall_score"),
                "interview_status": scorecard.get("interview_status"),
                "github_grounded_questions_asked": scorecard.get(
                    "github_grounded_questions_asked"
                ),
                "duration_seconds": scorecard.get("duration_seconds"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
