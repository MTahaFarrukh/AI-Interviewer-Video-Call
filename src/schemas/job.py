from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.enums import JobStatus


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="")
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    status: JobStatus = JobStatus.draft


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: str | None = None
    status: JobStatus | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    description: str
    status: JobStatus
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
