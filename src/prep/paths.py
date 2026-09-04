from __future__ import annotations

from pathlib import Path

from config import PREP_OUTPUT_DIR, QUESTION_PLAN_PATH, ROOT_DIR

INPUTS_DIR = ROOT_DIR / "inputs"
PROMPTS_DIR = ROOT_DIR / "prompts"
CHECKPOINT_DIR = PREP_OUTPUT_DIR
GITHUB_CACHE_DIR = PREP_OUTPUT_DIR / ".github_cache"
RESUME_JSON = PREP_OUTPUT_DIR / "resume.json"
JD_JSON = PREP_OUTPUT_DIR / "jd.json"
GITHUB_JSON = PREP_OUTPUT_DIR / "github.json"
PREP_QUESTION_PLAN = PREP_OUTPUT_DIR / "question_plan.json"
PROFILE_JSON = PREP_OUTPUT_DIR / "candidate_profile.json"
GAP_JSON = PREP_OUTPUT_DIR / "gap_analysis.json"


def ensure_output_dirs() -> None:
    PREP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GITHUB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    QUESTION_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
