from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.placeholders import AuthContext, get_current_user
from core.database import get_db
from repositories.applications import ApplicationRepository
from repositories.jobs import JobRepository
from schemas.application import ApplicationCreate, ApplicationRead, ApplicationUpdate

router = APIRouter(tags=["applications"])


@router.post(
    "/api/v1/jobs/{job_id}/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    job_id: uuid.UUID,
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> ApplicationRead:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    application = ApplicationRepository(db).create_for_job(job, payload)
    return ApplicationRead.model_validate(application)


@router.get(
    "/api/v1/jobs/{job_id}/applications",
    response_model=list[ApplicationRead],
)
def list_applications(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> list[ApplicationRead]:
    if JobRepository(db).get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return [
        ApplicationRead.model_validate(a)
        for a in ApplicationRepository(db).list_for_job(job_id)
    ]


@router.get("/api/v1/applications/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> ApplicationRead:
    application = ApplicationRepository(db).get(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return ApplicationRead.model_validate(application)


@router.patch("/api/v1/applications/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> ApplicationRead:
    repo = ApplicationRepository(db)
    application = repo.get(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return ApplicationRead.model_validate(repo.update(application, payload))
