from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.candidate import Candidate
from schemas.candidate import CandidateCreate, CandidateUpdate


class CandidateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, organization_id: uuid.UUID, payload: CandidateCreate) -> Candidate:
        candidate = Candidate(
            organization_id=organization_id,
            full_name=payload.full_name.strip(),
            email=str(payload.email).strip().lower(),
            phone=payload.phone,
            github_url=payload.github_url,
            linkedin_url=payload.linkedin_url,
            resume_url=payload.resume_url,
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def list_for_org(self, organization_id: uuid.UUID) -> list[Candidate]:
        stmt = (
            select(Candidate)
            .where(Candidate.organization_id == organization_id)
            .order_by(Candidate.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def get(self, candidate_id: uuid.UUID) -> Candidate | None:
        return self.db.get(Candidate, candidate_id)

    def update(self, candidate: Candidate, payload: CandidateUpdate) -> Candidate:
        data = payload.model_dump(exclude_unset=True)
        if "email" in data and data["email"] is not None:
            data["email"] = str(data["email"]).strip().lower()
        if "full_name" in data and data["full_name"] is not None:
            data["full_name"] = data["full_name"].strip()
        for key, value in data.items():
            setattr(candidate, key, value)
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate
