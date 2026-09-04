"""Live-interview controller. Slice 3: follow-ups + 8-minute time limit."""

from __future__ import annotations

import time
from typing import Any, Callable, Literal

from realtime.evaluate import Label, classify_answer

AdvanceAction = Literal["next", "follow_up", "wrap_up", "ignore"]
MAX_FOLLOW_UPS = 2
INTERVIEW_LIMIT_SECONDS = 480
_FOLLOW_UP_LABELS = frozenset({"shallow", "off_topic", "bluff"})


class InterviewController:
    def __init__(
        self,
        plan: dict[str, Any],
        clock: Callable[[], float] | None = None,
        persist: Callable[["InterviewController"], None] | None = None,
    ) -> None:
        self.plan = plan
        self.index = 0
        self.phase = "intro"
        self.completed_ids: list[str] = []
        self.follow_up_count = 0
        self.interview_start_time: float | None = None
        self.last_eval: Label | None = None
        self.last_answered_id = ""
        self._clock = clock or time.monotonic
        self._persist = persist
        self._awaiting_answer = False
        self._heard_speech_for_current = False
        self._candidate_speaking_now = False
        self._busy = False
        self._wrap_up_emitted = False
        self._transcript: list[dict[str, Any]] = []
        self._seen_turn_ids: set[str] = set()

    @property
    def questions(self) -> list[dict[str, Any]]:
        items = self.plan.get("questions") or []
        return [item for item in items if isinstance(item, dict)]

    @property
    def interview_duration(self) -> float:
        if self.interview_start_time is None:
            return 0.0
        return max(0.0, self._clock() - self.interview_start_time)

    def start_interview(self) -> None:
        if self.interview_start_time is None:
            self.interview_start_time = self._clock()
            self._touch()

    def _touch(self) -> None:
        if self._persist is None:
            return
        self._persist(self)

    def time_limit_reached(self) -> bool:
        if self.interview_start_time is None:
            return False
        return self.interview_duration >= INTERVIEW_LIMIT_SECONDS

    def should_wrap_up_now(self) -> bool:
        if self.phase == "wrap_up" or self._wrap_up_emitted:
            return False
        if not self.time_limit_reached():
            return False
        return not self._candidate_speaking_now

    def current_question(self) -> dict[str, Any] | None:
        if self.phase == "wrap_up":
            return None
        if not self.questions:
            return None
        if self.index < 0 or self.index >= len(self.questions):
            return None
        return self.questions[self.index]

    def current_question_id(self) -> str:
        question = self.current_question()
        if not question:
            return ""
        return str(question.get("id") or "").strip()

    def question_difficulty(self, question: dict[str, Any] | None = None) -> int:
        """Plan-order difficulty. Strong answers skip follow-ups and advance to a later item."""
        q = question if question is not None else self.current_question()
        if not q:
            return 0
        raw = q.get("difficulty")
        if raw is not None:
            try:
                value = int(raw)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        qid = str(q.get("id") or "").strip()
        for i, item in enumerate(self.questions):
            if str(item.get("id") or "").strip() == qid:
                return i + 1
        return int(self.index) + 1

    def restore_from_record(self, record: dict[str, Any] | None) -> None:
        """Reload live state after a dropped call. Does not rejoin LiveKit."""
        payload = record if isinstance(record, dict) else {}
        self.index = int(payload.get("current_question_index") or 0)
        self.phase = str(payload.get("phase") or "intro") or "intro"
        self.follow_up_count = int(payload.get("follow_up_count") or 0)
        completed = payload.get("completed_question_ids") or []
        self.completed_ids = [str(item) for item in completed if str(item).strip()]
        turns = payload.get("transcript") or []
        self._transcript = [dict(item) for item in turns if isinstance(item, dict)]
        self.last_answered_id = str(payload.get("current_question_id") or "")
        elapsed = float(payload.get("elapsed_seconds") or 0.0)
        self.interview_start_time = self._clock() - max(0.0, elapsed)
        self._wrap_up_emitted = self.phase == "wrap_up"
        self._awaiting_answer = self.phase in {"intro", "question"}
        self._heard_speech_for_current = False
        self._candidate_speaking_now = False
        self._busy = False
        self._seen_turn_ids = set()
        for turn in self._transcript:
            event_id = str(turn.get("event_id") or "").strip()
            if event_id:
                self._seen_turn_ids.add(event_id)
        if self.phase != "wrap_up" and self.index >= len(self.questions) and self.questions:
            self.index = len(self.questions) - 1

    def note_question_asked(self) -> None:
        if self.phase == "wrap_up":
            return
        self._awaiting_answer = True
        self._heard_speech_for_current = False
        if self.phase == "intro":
            self.phase = "question"

    def mark_candidate_speaking(self) -> None:
        self._candidate_speaking_now = True
        if self._awaiting_answer and self.phase != "wrap_up":
            self._heard_speech_for_current = True

    def mark_candidate_stopped(self) -> None:
        self._candidate_speaking_now = False

    def begin_wrap_up(self) -> bool:
        self.phase = "wrap_up"
        if self._wrap_up_emitted:
            return False
        self._wrap_up_emitted = True
        self._touch()
        return True

    def get_transcript(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._transcript]

    def record_turn(
        self,
        speaker: str,
        text: str,
        turn_type: str,
        question_id: str | None = None,
        event_id: str = "",
        timestamp: float | None = None,
    ) -> bool:
        """Record one completed turn. Returns False if ignored as duplicate/empty."""
        cleaned = (text or "").strip()
        if not cleaned:
            return False
        if speaker not in {"interviewer", "candidate"}:
            return False
        if turn_type not in {"question", "answer", "follow_up", "closing"}:
            return False
        key = event_id.strip()
        if key:
            if key in self._seen_turn_ids:
                return False
            self._seen_turn_ids.add(key)
        qid = (question_id if question_id is not None else self.current_question_id()).strip()
        if speaker == "candidate" and turn_type == "answer" and not qid:
            qid = self.last_answered_id
        ts = self._clock() if timestamp is None else timestamp
        self._transcript.append(
            {
                "speaker": speaker,
                "text": cleaned,
                "timestamp": ts,
                "question_id": qid,
                "turn_type": turn_type,
            }
        )
        self._touch()
        return True

    def record_interviewer_turn(self, text: str, turn_type: str = "question") -> bool:
        qid = "" if turn_type == "closing" else self.current_question_id()
        return self.record_turn("interviewer", text, turn_type, question_id=qid)

    def try_complete_answer(self, answer_text: str = "", event_id: str = "") -> AdvanceAction:
        """One completed candidate turn: one eval, then follow-up or advance or wrap-up."""
        if self._busy or self.phase == "wrap_up":
            return "ignore"
        if not self._awaiting_answer or not self._heard_speech_for_current:
            return "ignore"
        if self.current_question() is None:
            return "ignore"
        self._busy = True
        try:
            self._awaiting_answer = False
            self._heard_speech_for_current = False
            self._candidate_speaking_now = False
            question = self.current_question() or {}
            qid = self.current_question_id()
            self.last_answered_id = qid
            self.record_turn(
                "candidate",
                answer_text,
                "answer",
                question_id=qid,
                event_id=event_id,
            )
            if self.time_limit_reached():
                self.last_eval = classify_answer(answer_text, question)
                self.begin_wrap_up()
                return "wrap_up"
            label = classify_answer(answer_text, question)
            self.last_eval = label
            if label in _FOLLOW_UP_LABELS and self.follow_up_count < MAX_FOLLOW_UPS:
                self.follow_up_count += 1
                self._touch()
                return "follow_up"
            nxt = self.advance()
            if nxt is None:
                self.begin_wrap_up()
                return "wrap_up"
            self._touch()
            return "next"
        finally:
            self._busy = False

    def advance(self) -> dict[str, Any] | None:
        if self.phase == "wrap_up":
            return None
        qid = self.current_question_id()
        if qid and qid not in self.completed_ids:
            self.completed_ids.append(qid)
        last = len(self.questions) - 1
        if last < 0 or self.index >= last:
            self.phase = "wrap_up"
            self.follow_up_count = 0
            return None
        self.index += 1
        self.phase = "question"
        self.follow_up_count = 0
        return self.current_question()
