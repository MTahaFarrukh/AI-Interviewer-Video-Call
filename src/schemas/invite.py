from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.enums import InterviewStatus, InviteStatus


class InviteCreateRequest(BaseModel):
    ttl_hours: int = Field(default=72, ge=1, le=24 * 30)


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interview_id: uuid.UUID
    status: InviteStatus
    expires_at: datetime
    opened_at: datetime | None
    accepted_at: datetime | None
    completed_at: datetime | None
    consent_accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InviteCreatedResponse(BaseModel):
    invite: InviteRead
    invite_url_path: str
    raw_token: str
    share_note: str = (
        "Copy and share this link with the candidate. "
        "Email delivery is not integrated yet."
    )


class PublicInviteRead(BaseModel):
    invite_status: InviteStatus
    can_begin_setup: bool
    can_enter_room: bool
    expires_at: datetime
    candidate_name: str
    organization_name: str
    job_title: str
    expected_duration_seconds: int
    interview_status: InterviewStatus
    consent_accepted: bool
    message: str | None = None


class ConsentAcceptRequest(BaseModel):
    accepted: bool = True


class SessionStartResponse(BaseModel):
    room_name: str
    participant_identity: str
    livekit_url: str
    token: str
    interview_id: str
    expected_duration_seconds: int
    questions_total: int | None = None
