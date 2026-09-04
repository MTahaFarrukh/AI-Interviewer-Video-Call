"""Evaluate a completed interview transcript. Does not join LiveKit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import QUESTION_PLAN_PATH, ROOT_DIR
from plan_loader import load_approved_plan
from prep.io import read_json, write_json
from prep.paths import GAP_JSON, PROFILE_JSON
from realtime.evaluate_interview import evaluate_interview

DEFAULT_TRANSCRIPT = ROOT_DIR / "src" / "realtime" / "sample_transcript.json"
DEFAULT_OUT = ROOT_DIR / "output" / "interview_evaluation.json"


def _load_optional(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a completed FirstRound interview transcript (offline)."
    )
    parser.add_argument("--plan", default=str(QUESTION_PLAN_PATH), help="Approved question_plan.json")
    parser.add_argument(
        "--transcript",
        default=str(DEFAULT_TRANSCRIPT),
        help="Completed transcript JSON (fixture is fine)",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Where to write evaluation JSON")
    args = parser.parse_args(argv)

    plan = load_approved_plan(Path(args.plan))
    if not plan:
        print("No approved question plan.", file=sys.stderr)
        return 1
    transcript_path = Path(args.transcript)
    if not transcript_path.is_file():
        print(f"Transcript not found: {transcript_path}", file=sys.stderr)
        return 1
    payload = read_json(transcript_path)
    transcript = payload if isinstance(payload, list) else payload.get("turns") or payload.get("transcript")
    if not isinstance(transcript, list):
        print("Transcript must be a list of turns.", file=sys.stderr)
        return 1
    result = evaluate_interview(
        plan,
        transcript,
        profile=_load_optional(PROFILE_JSON),
        gap=_load_optional(GAP_JSON) or plan.get("gap_analysis"),
    )
    out = Path(args.out)
    write_json(out, result)
    print(json.dumps(
        {
            "out": str(out),
            "overall_score": result.get("overall_score"),
            "recommendation": result.get("recommendation"),
            "questions": len(result.get("question_results") or []),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
