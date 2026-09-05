from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.placeholders import AuthContext, get_current_user
from core.database import get_db
from repositories.organizations import OrganizationRepository
from schemas.organization import OrganizationCreate, OrganizationRead

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> OrganizationRead:
    repo = OrganizationRepository(db)
    if repo.get_by_slug(payload.slug) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
    try:
        return OrganizationRead.model_validate(repo.create(payload))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Organization conflict"
        ) from exc


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> list[OrganizationRead]:
    return [OrganizationRead.model_validate(o) for o in OrganizationRepository(db).list()]


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> OrganizationRead:
    org = OrganizationRepository(db).get(organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationRead.model_validate(org)
