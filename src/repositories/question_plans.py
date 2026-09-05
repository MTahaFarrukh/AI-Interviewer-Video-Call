from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from core.enums import QuestionPlanStatus
from models.interview import Interview
from models.question import Question
from models.question_plan import QuestionPlan


class QuestionPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_latest_for_interview(self, interview_id: uuid.UUID) -> QuestionPlan | None:
        stmt = (
            select(QuestionPlan)
            .where(QuestionPlan.interview_id == interview_id)
            .options(selectinload(QuestionPlan.questions))
            .order_by(QuestionPlan.version.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def next_version(self, interview_id: uuid.UUID) -> int:
        latest = self.get_latest_for_interview(interview_id)
        return 1 if latest is None else latest.version + 1

    def save_plan_dict(
        self,
        interview: Interview,
        plan: dict[str, Any],
        *,
        status: QuestionPlanStatus = QuestionPlanStatus.generated,
        source: str | None = "api",
    ) -> QuestionPlan:
        """Persist an engine-shaped plan dict into QuestionPlan + Question rows."""
        version = self.next_version(interview.id)
        if status == QuestionPlanStatus.approved:
            self._supersede_approved(interview.id)

        approved_at = None
        if status == QuestionPlanStatus.approved or plan.get("approved_by_human"):
            status = QuestionPlanStatus.approved
            approved_at = datetime.now(timezone.utc)

        qp = QuestionPlan(
            interview_id=interview.id,
            version=version,
            status=status,
            source=source,
            recruiter_approved_at=approved_at,
        )
        self.db.add(qp)
        self.db.flush()

        questions = plan.get("questions") or []
        for index, item in enumerate(questions, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("question") or item.get("text") or item.get("question_text") or "")
            if not text.strip():
                continue
            position = int(item.get("position") or index)
            meta = {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "question",
                    "text",
                    "question_text",
                    "competency",
                    "difficulty",
                    "rationale",
                    "position",
                    "max_followups",
                }
            }
            self.db.add(
                Question(
                    question_plan_id=qp.id,
                    position=position,
                    question_text=text.strip(),
                    competency=(str(item.get("competency") or item.get("category") or "") or None),
                    difficulty=str(item.get("difficulty") or "") or None,
                    rationale=str(item.get("rationale") or "") or None,
                    max_followups=int(item.get("max_followups") or 2),
                    metadata_json=meta or None,
                )
            )
        self.db.commit()
        return self.get_latest_for_interview(interview.id)  # type: ignore[return-value]

    def _supersede_approved(self, interview_id: uuid.UUID) -> None:
        stmt = select(QuestionPlan).where(
            QuestionPlan.interview_id == interview_id,
            QuestionPlan.status == QuestionPlanStatus.approved,
        )
        for plan in self.db.scalars(stmt):
            plan.status = QuestionPlanStatus.superseded
            self.db.add(plan)

    def to_engine_dict(self, plan: QuestionPlan) -> dict[str, Any]:
        questions = []
        for q in sorted(plan.questions, key=lambda item: item.position):
            item: dict[str, Any] = {
                "id": f"q{q.position}",
                "position": q.position,
                "question": q.question_text,
                "text": q.question_text,
                "competency": q.competency or "",
                "difficulty": q.difficulty or "",
                "rationale": q.rationale or "",
                "max_followups": q.max_followups,
            }
            if q.metadata_json:
                item.update(q.metadata_json)
            questions.append(item)
        return {
            "questions": questions,
            "approved_by_human": plan.status == QuestionPlanStatus.approved,
            "approval_status": (
                "approved" if plan.status == QuestionPlanStatus.approved else plan.status.value
            ),
            "version": plan.version,
            "source": plan.source,
        }
