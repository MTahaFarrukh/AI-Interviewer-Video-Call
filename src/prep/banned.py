"""Banned interview topics from the FirstRound specification."""

from __future__ import annotations

import re

BANNED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("age", re.compile(r"\b(how old|age|birthday|date of birth|year you were born)\b", re.I)),
    ("gender", re.compile(r"\b(gender|male or female|man or woman)\b", re.I)),
    ("marital", re.compile(r"\b(marital|married|spouse|husband|wife|children|kids)\b", re.I)),
    ("religion", re.compile(r"\b(religion|religious|muslim|christian|hindu|church|mosque)\b", re.I)),
    ("nationality", re.compile(r"\b(nationality|citizenship|where were you born|what country are you from)\b", re.I)),
    ("health", re.compile(r"\b(health|pregnant|pregnancy|disability|medical condition|illness)\b", re.I)),
    ("salary_history", re.compile(r"\b(salary history|current salary|how much do you (make|earn)|previous salary)\b", re.I)),
    ("politics", re.compile(r"\b(political|politics|political party|who did you vote)\b", re.I)),
)


def banned_hits(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in BANNED_PATTERNS:
        if pattern.search(text or ""):
            hits.append(label)
    return hits


SAFE_REPLACEMENT_QUESTION = (
    "Walk me through a recent technical decision you made for this role, "
    "including one trade-off and why you chose it."
)


def sanitize_spoken_question(text: str) -> dict:
    """Block banned topics before they can be spoken to the candidate."""
    original = text or ""
    hits = banned_hits(original)
    if not hits:
        return {
            "allowed": True,
            "text": original,
            "original": original,
            "blocked": False,
            "flags": [],
        }
    flag = {
        "type": "banned_question",
        "categories": hits,
        "original": original,
        "replacement": SAFE_REPLACEMENT_QUESTION,
    }
    return {
        "allowed": False,
        "text": SAFE_REPLACEMENT_QUESTION,
        "original": original,
        "blocked": True,
        "flags": [flag],
    }
