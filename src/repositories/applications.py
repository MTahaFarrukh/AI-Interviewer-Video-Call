from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.application import Application
from models.candidate import Candidate
from models.job import Job
from schemas.application import ApplicationCreate, ApplicationUpdate


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_for_job(self, job: Job, payload: ApplicationCreate) -> Application:
        candidate = self.db.get(Candidate, payload.candidate_id)
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
        if candidate.organization_id != job.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidate and job belong to different organizations",
            )
        existing = self.db.scalar(
            select(Application).where(
                Application.job_id == job.id,
                Application.candidate_id == candidate.id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application already exists for this candidate and job",
            )
        application = Application(
            organization_id=job.organization_id,
            job_id=job.id,
            candidate_id=candidate.id,
            status=payload.status,
        )
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application

    def list_for_job(self, job_id: uuid.UUID) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.job_id == job_id)
            .order_by(Application.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def get(self, application_id: uuid.UUID) -> Application | None:
        return self.db.get(Application, application_id)

    def update(self, application: Application, payload: ApplicationUpdate) -> Application:
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(application, key, value)
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application
