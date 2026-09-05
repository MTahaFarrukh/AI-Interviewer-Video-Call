from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.organization import Organization
from schemas.organization import OrganizationCreate


class OrganizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: OrganizationCreate) -> Organization:
        org = Organization(name=payload.name.strip(), slug=payload.slug.strip().lower())
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def list(self) -> list[Organization]:
        return list(self.db.scalars(select(Organization).order_by(Organization.created_at.desc())))

    def get(self, organization_id: uuid.UUID) -> Organization | None:
        return self.db.get(Organization, organization_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.db.scalar(select(Organization).where(Organization.slug == slug.lower()))
