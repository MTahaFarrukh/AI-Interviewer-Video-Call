"""Export the live transcript into the PDF grading schema. Does not invent turns."""

from __future__ import annotations

from typing import Any

SPEAKER_MAP = {
    "interviewer": "agent",
    "agent": "agent",
    "candidate": "candidate",
}


def _as_turns(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        turns = payload.get("turns") or payload.get("transcript") or []
        if isinstance(turns, list):
            return [item for item in turns if isinstance(item, dict)]
    return []


def _timestamp_ms(raw: Any, origin: float | None) -> int:
    if not isinstance(raw, (int, float)):
        return 0
    value = float(raw)
    if value >= 1_000_000_000_000:
        return int(value)
    if value >= 1_000_000_000:
        return int(value * 1000)
    if origin is None:
        return int(round(value * 1000))
    return max(0, int(round((value - origin) * 1000)))


def export_transcript(payload: Any) -> dict[str, Any]:
    source = _as_turns(payload)
    stamps = [float(t["timestamp"]) for t in source if isinstance(t.get("timestamp"), (int, float))]
    origin = min(stamps) if stamps else None
    turns: list[dict[str, Any]] = []
    for item in source:
        speaker = SPEAKER_MAP.get(str(item.get("speaker") or "").strip().lower(), "")
        if speaker not in {"agent", "candidate"}:
            continue
        text = str(item.get("text") or "")
        qid = str(item.get("question_id") or "").strip()
        turn_type = str(item.get("turn_type") or "").strip()
        node = qid or turn_type or ""
        if turn_type == "closing":
            node = "wrap_up"
        turns.append(
            {
                "speaker": speaker,
                "text": text,
                "timestamp_ms": _timestamp_ms(item.get("timestamp"), origin),
                "node": node,
                "interrupted": bool(item.get("interrupted", False)),
            }
        )
    return {"turns": turns}
