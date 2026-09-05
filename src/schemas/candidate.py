from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    resume_url: str | None = None


class CandidateUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    resume_url: str | None = None


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    github_url: str | None
    linkedin_url: str | None
    resume_url: str | None
    created_at: datetime
    updated_at: datetime
