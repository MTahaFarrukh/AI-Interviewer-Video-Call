from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from core.enums import ApplicationStatus


class ApplicationCreate(BaseModel):
    candidate_id: uuid.UUID
    status: ApplicationStatus = ApplicationStatus.pending


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
