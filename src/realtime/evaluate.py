"""Lightweight heuristic answer labels. Not a hiring score."""

from __future__ import annotations

import re
from typing import Any, Literal

Label = Literal["strong", "adequate", "shallow", "off_topic", "bluff"]

_STOP = frozenset(
    """
    a an the and or to of in on for with from by as at is are was were be been
    it this that these those you your we our they their i me my we us how what
    when where why which who can could would should do did does about into over
    specifically walk tell describe please
    """.split()
)
_REASONING = (
    "because",
    "so that",
    "therefore",
    "in order to",
    "i chose",
    "trade-off",
    "tradeoff",
    "the reason",
    "that's why",
    "that is why",
)
_VAGUE = frozenset(
    "yeah yes no ok okay stuff things whatever maybe dunno idk sure um uh".split()
)
_FILE_RE = re.compile(r"\b[\w./\\-]+\.(?:py|ts|tsx|js|jsx|go|java|rs|md)\b", re.I)
_COMMIT_RE = re.compile(r"\b[a-f0-9]{7,40}\b", re.I)
_CLAIM_RE = re.compile(
    r"\b(i|we)\s+(wrote|changed|implemented|authored|committed|built|shipped)\b",
    re.I,
)


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if tok not in _STOP and len(tok) > 2}


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _has_reasoning(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _REASONING)


def _has_concrete(text: str) -> bool:
    return bool(re.search(r"\d", text) or _FILE_RE.search(text) or re.search(
        r"\b(chroma|fastapi|chunk|embedding|langchain|sqlite|commit|function|endpoint)\b",
        text,
        re.I,
    ))


def _is_bluff(answer: str, question: dict[str, Any]) -> bool:
    if not _CLAIM_RE.search(answer):
        return False
    approved_file = str(question.get("file") or "").replace("\\", "/").lower()
    claimed_files = [m.group(0).replace("\\", "/").lower() for m in _FILE_RE.finditer(answer)]
    if approved_file and claimed_files:
        if not any(path in approved_file or approved_file in path for path in claimed_files):
            return True
    if claimed_files and not approved_file:
        evidence = str(question.get("evidence") or question.get("source_reference") or "").lower()
        if evidence and not any(path.split("/")[-1] in evidence for path in claimed_files):
            return True
    approved_commit = str(question.get("commit") or "").lower()
    claimed_commits = [m.group(0).lower() for m in _COMMIT_RE.finditer(answer)]
    if approved_commit and claimed_commits:
        if not any(item in approved_commit or approved_commit.startswith(item) for item in claimed_commits):
            return True
    return False


def classify_answer(answer: str, question: dict[str, Any] | None = None) -> Label:
    text = (answer or "").strip()
    question = question or {}
    wc = _word_count(text)
    if wc == 0:
        return "shallow"
    qtext = " ".join(
        str(question.get(key) or "")
        for key in ("question", "text", "expected_evidence", "competency", "source_reference")
    )
    q_tokens = _tokens(qtext)
    a_tokens = _tokens(text)
    overlap = (len(q_tokens & a_tokens) / len(q_tokens)) if q_tokens else 0.0
    content_words = [w.lower() for w in re.findall(r"[a-zA-Z']+", text) if w.lower() not in _STOP]
    vague_ratio = (
        sum(1 for w in content_words if w in _VAGUE) / len(content_words) if content_words else 1.0
    )

    if _is_bluff(text, question):
        return "bluff"
    if wc < 12 or vague_ratio > 0.6:
        return "shallow"
    if q_tokens and overlap < 0.06 and wc >= 12:
        return "off_topic"
    if wc >= 35 and overlap >= 0.12 and _has_reasoning(text) and _has_concrete(text):
        return "strong"
    if wc >= 20 and overlap >= 0.08:
        return "adequate"
    if q_tokens and overlap < 0.08:
        return "off_topic"
    return "shallow"
