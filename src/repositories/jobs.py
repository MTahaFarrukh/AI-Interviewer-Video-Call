from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.job import Job
from schemas.job import JobCreate, JobUpdate


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        organization_id: uuid.UUID,
        payload: JobCreate,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> Job:
        job = Job(
            organization_id=organization_id,
            title=payload.title.strip(),
            description=payload.description,
            department=payload.department,
            location=payload.location,
            employment_type=payload.employment_type,
            status=payload.status,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def list_for_org(self, organization_id: uuid.UUID) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.organization_id == organization_id)
            .order_by(Job.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)

    def update(self, job: Job, payload: JobUpdate) -> Job:
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(job, key, value.strip() if isinstance(value, str) and key == "title" else value)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
