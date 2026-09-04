"""Generate a recruiter-facing interview report. Does not join LiveKit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import (
    INTERVIEW_EVALUATION_PATH,
    INTERVIEW_REPORT_JSON_PATH,
    INTERVIEW_REPORT_MD_PATH,
    INTERVIEW_TRANSCRIPT_PATH,
    QUESTION_PLAN_PATH,
)
from plan_loader import load_approved_plan
from prep.io import read_json, write_json
from prep.paths import GAP_JSON, PROFILE_JSON
from realtime.evaluate_interview import evaluate_interview
from realtime.report import generate_report, render_markdown
from realtime.store import InterviewStore


def _load_optional(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


def _load_transcript(path: Path) -> list | dict:
    payload = read_json(path)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload
    raise ValueError("Transcript must be a JSON list or object with turns.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a FirstRound recruiter report from plan, transcript, and evaluation."
    )
    parser.add_argument("--plan", default=str(QUESTION_PLAN_PATH))
    parser.add_argument("--transcript", default=str(INTERVIEW_TRANSCRIPT_PATH))
    parser.add_argument("--evaluation", default=str(INTERVIEW_EVALUATION_PATH))
    parser.add_argument("--out-json", default=str(INTERVIEW_REPORT_JSON_PATH))
    parser.add_argument("--out-md", default=str(INTERVIEW_REPORT_MD_PATH))
    parser.add_argument("--interview-id", default="", help="Load transcript from the live interview SQLite store")
    parser.add_argument("--store", default="", help="Optional SQLite path for --interview-id")
    args = parser.parse_args(argv)

    plan_path = Path(args.plan)
    if not plan_path.is_file():
        print(f"plan not found: {plan_path}", file=sys.stderr)
        return 1
    plan = read_json(plan_path)
    if not isinstance(plan, dict):
        print("Plan must be a JSON object.", file=sys.stderr)
        return 1

    interview_id = str(args.interview_id or "").strip()
    if interview_id:
        store = InterviewStore(Path(args.store) if args.store else None)
        record = store.get_interview(interview_id)
        if not record:
            print(f"Interview not found: {interview_id}", file=sys.stderr)
            return 1
        transcript = record.get("transcript") or []
        if not isinstance(transcript, list):
            print("Persisted transcript is invalid.", file=sys.stderr)
            return 1
        evaluation_path = Path(args.evaluation)
        if evaluation_path.is_file():
            evaluation = read_json(evaluation_path)
        else:
            approved = load_approved_plan(plan_path) or plan
            evaluation = evaluate_interview(
                approved,
                transcript,
                profile=_load_optional(PROFILE_JSON),
                gap=_load_optional(GAP_JSON) or plan.get("gap_analysis"),
            )
            write_json(evaluation_path, evaluation)
    else:
        transcript_path = Path(args.transcript)
        evaluation_path = Path(args.evaluation)
        for path, label in (
            (transcript_path, "transcript"),
            (evaluation_path, "evaluation"),
        ):
            if not path.is_file():
                print(f"{label} not found: {path}", file=sys.stderr)
                return 1
        evaluation = read_json(evaluation_path)
        try:
            transcript = _load_transcript(transcript_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Could not read transcript: {exc}", file=sys.stderr)
            return 1

    if not isinstance(evaluation, dict):
        print("Evaluation must be a JSON object.", file=sys.stderr)
        return 1
    if isinstance(transcript, dict):
        transcript = transcript.get("turns") or transcript.get("transcript") or []
    if not isinstance(transcript, list):
        print("Transcript must be a list of turns.", file=sys.stderr)
        return 1

    report = generate_report(plan, transcript, evaluation)
    json_out = Path(args.out_json)
    md_out = Path(args.out_md)
    write_json(json_out, report)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_out),
                "markdown": str(md_out),
                "candidate": (report.get("candidate") or {}).get("name"),
                "recommendation": (report.get("decision") or {}).get("recommendation"),
                "overall_score": (report.get("decision") or {}).get("overall_score"),
                "interview_status": report.get("interview_status"),
                "sample_mode": (report.get("metadata") or {}).get("sample_mode"),
                "interview_id": interview_id or None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
