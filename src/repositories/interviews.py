from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models.application import Application
from models.interview import Interview
from models.question_plan import QuestionPlan
from schemas.interview import InterviewCreate, InterviewUpdate


class InterviewRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_for_application(
        self, application: Application, payload: InterviewCreate
    ) -> Interview:
        interview = Interview(
            organization_id=application.organization_id,
            application_id=application.id,
            status=payload.status,
            livekit_room_name=payload.livekit_room_name,
        )
        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def get(self, interview_id: uuid.UUID) -> Interview | None:
        return self.db.get(Interview, interview_id)

    def list_for_org(self, organization_id: uuid.UUID) -> list[Interview]:
        stmt = (
            select(Interview)
            .where(Interview.organization_id == organization_id)
            .order_by(Interview.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def update(self, interview: Interview, payload: InterviewUpdate) -> Interview:
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(interview, key, value)
        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def get_latest_question_plan(self, interview_id: uuid.UUID) -> QuestionPlan | None:
        stmt = (
            select(QuestionPlan)
            .where(QuestionPlan.interview_id == interview_id)
            .options(selectinload(QuestionPlan.questions))
            .order_by(QuestionPlan.version.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)
