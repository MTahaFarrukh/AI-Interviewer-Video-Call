from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.placeholders import AuthContext, get_current_user
from core.database import get_db
from repositories.jobs import JobRepository
from repositories.organizations import OrganizationRepository
from schemas.job import JobCreate, JobRead, JobUpdate

router = APIRouter(tags=["jobs"])


@router.post(
    "/api/v1/organizations/{organization_id}/jobs",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    organization_id: uuid.UUID,
    payload: JobCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
) -> JobRead:
    if OrganizationRepository(db).get(organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    job = JobRepository(db).create(
        organization_id, payload, created_by_user_id=auth.user_id
    )
    return JobRead.model_validate(job)


@router.get(
    "/api/v1/organizations/{organization_id}/jobs",
    response_model=list[JobRead],
)
def list_jobs(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> list[JobRead]:
    if OrganizationRepository(db).get(organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return [JobRead.model_validate(j) for j in JobRepository(db).list_for_org(organization_id)]


@router.get("/api/v1/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> JobRead:
    job = JobRepository(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobRead.model_validate(job)


@router.patch("/api/v1/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> JobRead:
    repo = JobRepository(db)
    job = repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobRead.model_validate(repo.update(job, payload))
