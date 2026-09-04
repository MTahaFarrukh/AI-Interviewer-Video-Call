"""Gemini Flash structured JSON helper for the prep graph."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from config import load_prep_settings

logger = logging.getLogger("firstround.prep.llm")

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)
_LLM_DISABLED_REASON = ""


class LlmError(RuntimeError):
    pass


def generate_json(prompt: str, *, temperature: float = 0.2) -> Any:
    global _LLM_DISABLED_REASON
    if _LLM_DISABLED_REASON:
        raise LlmError(f"Gemini structured output failed: {_LLM_DISABLED_REASON}")
    settings = load_prep_settings()
    client = genai.Client(api_key=settings.google_api_key)
    last_error = "unknown"
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=settings.gemini_text_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            text = (response.text or "").strip()
            if not text:
                last_error = "empty model response"
                continue
            return _parse_json(text)
        except Exception as exc:
            last_error = _safe_error(exc)
            logger.warning("Gemini JSON attempt %s failed: %s", attempt + 1, last_error)
            if last_error == "invalid_google_api_key":
                _LLM_DISABLED_REASON = last_error
                break
    raise LlmError(f"Gemini structured output failed: {last_error}")


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "api key not valid" in lowered or "api_key_invalid" in lowered:
        return "invalid_google_api_key"
    if "429" in text or "resource exhausted" in lowered:
        return "gemini_rate_limited"
    return type(exc).__name__


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_FENCE.search(text)
        if match:
            return json.loads(match.group(1))
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise LlmError("Model did not return valid JSON")
