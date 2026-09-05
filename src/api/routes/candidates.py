from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.placeholders import AuthContext, get_current_user
from core.database import get_db
from repositories.candidates import CandidateRepository
from repositories.organizations import OrganizationRepository
from schemas.candidate import CandidateCreate, CandidateRead, CandidateUpdate

router = APIRouter(tags=["candidates"])


@router.post(
    "/api/v1/organizations/{organization_id}/candidates",
    response_model=CandidateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate(
    organization_id: uuid.UUID,
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> CandidateRead:
    if OrganizationRepository(db).get(organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    try:
        candidate = CandidateRepository(db).create(organization_id, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate with this email already exists in the organization",
        ) from exc
    return CandidateRead.model_validate(candidate)


@router.get(
    "/api/v1/organizations/{organization_id}/candidates",
    response_model=list[CandidateRead],
)
def list_candidates(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> list[CandidateRead]:
    if OrganizationRepository(db).get(organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return [
        CandidateRead.model_validate(c)
        for c in CandidateRepository(db).list_for_org(organization_id)
    ]


@router.get("/api/v1/candidates/{candidate_id}", response_model=CandidateRead)
def get_candidate(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> CandidateRead:
    candidate = CandidateRepository(db).get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return CandidateRead.model_validate(candidate)


@router.patch("/api/v1/candidates/{candidate_id}", response_model=CandidateRead)
def update_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateUpdate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> CandidateRead:
    repo = CandidateRepository(db)
    candidate = repo.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    try:
        updated = repo.update(candidate, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate with this email already exists in the organization",
        ) from exc
    return CandidateRead.model_validate(updated)
