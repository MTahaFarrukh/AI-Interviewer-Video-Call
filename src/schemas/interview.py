from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.enums import InterviewStatus, QuestionPlanStatus


class InterviewCreate(BaseModel):
    status: InterviewStatus = InterviewStatus.draft
    livekit_room_name: str | None = None


class InterviewUpdate(BaseModel):
    status: InterviewStatus | None = None
    livekit_room_name: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)


class InterviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    application_id: uuid.UUID
    status: InterviewStatus
    livekit_room_name: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    created_at: datetime
    updated_at: datetime


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    question_text: str
    competency: str | None
    difficulty: str | None
    rationale: str | None
    max_followups: int
    metadata_json: dict | None = Field(default=None, validation_alias="metadata_json")


class QuestionPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interview_id: uuid.UUID
    version: int
    status: QuestionPlanStatus
    source: str | None
    recruiter_approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionRead] = []


class QuestionPlanNotReady(BaseModel):
    interview_id: uuid.UUID
    status: str = "not_ready"
    detail: str = "No question plan stored for this interview yet"
