"""Phase 1 configuration. Never log secret values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
GEMINI_TEXT_MODEL = "gemini-flash-latest"
AGENT_NAME = "firstround-interviewer"
DEFAULT_MODE = "voice"
SUPPORTED_MODES = frozenset({"voice"})
QUESTION_PLAN_PATH = ROOT_DIR / "output" / "question_plan.json"
INTERVIEW_TRANSCRIPT_PATH = ROOT_DIR / "output" / "interview_transcript.json"
INTERVIEW_EVALUATION_PATH = ROOT_DIR / "output" / "interview_evaluation.json"
INTERVIEW_REPORT_JSON_PATH = ROOT_DIR / "output" / "interview_report.json"
INTERVIEW_REPORT_MD_PATH = ROOT_DIR / "output" / "interview_report.md"
PDF_TRANSCRIPT_PATH = ROOT_DIR / "output" / "transcript.json"
PDF_SCORECARD_PATH = ROOT_DIR / "output" / "scorecard.json"
PDF_REPORT_PATH = ROOT_DIR / "output" / "report.pdf"
LIVE_OUTPUT_DIR = ROOT_DIR / "output" / "live"
INTERVIEW_STORE_PATH = LIVE_OUTPUT_DIR / "interview.sqlite"
PREP_OUTPUT_DIR = ROOT_DIR / "output" / "prep"
CHECKPOINT_PATH = PREP_OUTPUT_DIR / "langgraph.sqlite"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    google_api_key: str
    mode: str
    gemini_model: str = GEMINI_LIVE_MODEL
    agent_name: str = AGENT_NAME

    @classmethod
    def load(cls) -> Settings:
        required = (
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
            "GOOGLE_API_KEY",
        )
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ConfigError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        mode = os.getenv("FIRSTROUND_MODE", DEFAULT_MODE).strip().lower() or DEFAULT_MODE
        if mode != "voice":
            raise ConfigError(
                f"Phase 1 only supports FIRSTROUND_MODE=voice (got {mode!r}). "
                "Vendor avatar mode is not implemented yet."
            )

        return cls(
            livekit_url=_clean_env("LIVEKIT_URL"),
            livekit_api_key=_clean_env("LIVEKIT_API_KEY"),
            livekit_api_secret=_clean_env("LIVEKIT_API_SECRET"),
            google_api_key=_clean_env("GOOGLE_API_KEY"),
            mode=mode,
        )


def load_settings() -> Settings:
    return Settings.load()


@dataclass(frozen=True)
class PrepSettings:
    """Keys needed by the Phase 2 prep graph. LiveKit is not required here."""

    google_api_key: str
    github_token: str
    gemini_text_model: str = GEMINI_TEXT_MODEL

    @classmethod
    def load(cls) -> PrepSettings:
        google_api_key = _clean_env("GOOGLE_API_KEY")
        if not google_api_key:
            raise ConfigError("Missing required environment variable: GOOGLE_API_KEY")
        return cls(
            google_api_key=google_api_key,
            github_token=_clean_env("GITHUB_TOKEN"),
        )


def _clean_env(name: str) -> str:
    return os.getenv(name, "").strip().strip("\"'")


def load_prep_settings() -> PrepSettings:
    return PrepSettings.load()
