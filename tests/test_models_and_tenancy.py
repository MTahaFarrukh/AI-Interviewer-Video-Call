from __future__ import annotations

import uuid

from core.enums import ApplicationStatus, JobStatus
from schemas.application import ApplicationCreate
from schemas.candidate import CandidateCreate
from schemas.job import JobCreate
from schemas.organization import OrganizationCreate
from repositories.applications import ApplicationRepository
from repositories.candidates import CandidateRepository
from repositories.jobs import JobRepository
from repositories.organizations import OrganizationRepository
from repositories.interviews import InterviewRepository
from schemas.interview import InterviewCreate
from fastapi import HTTPException
import pytest


def test_organization_job_candidate_application_interview_chain(db_session) -> None:
    org = OrganizationRepository(db_session).create(
        OrganizationCreate(name="Acme", slug="acme")
    )
    job = JobRepository(db_session).create(
        org.id, JobCreate(title="Backend Engineer", description="APIs", status=JobStatus.active)
    )
    candidate = CandidateRepository(db_session).create(
        org.id,
        CandidateCreate(full_name="Sam Example", email="sam@example.com"),
    )
    application = ApplicationRepository(db_session).create_for_job(
        job, ApplicationCreate(candidate_id=candidate.id, status=ApplicationStatus.pending)
    )
    interview = InterviewRepository(db_session).create_for_application(
        application, InterviewCreate()
    )
    assert application.organization_id == org.id
    assert interview.organization_id == org.id
    assert interview.application_id == application.id


def test_cross_organization_application_rejected(db_session) -> None:
    org_a = OrganizationRepository(db_session).create(
        OrganizationCreate(name="Org A", slug="org-a")
    )
    org_b = OrganizationRepository(db_session).create(
        OrganizationCreate(name="Org B", slug="org-b")
    )
    job = JobRepository(db_session).create(
        org_a.id, JobCreate(title="Role", description="x")
    )
    candidate = CandidateRepository(db_session).create(
        org_b.id,
        CandidateCreate(full_name="Other", email="other@example.com"),
    )
    with pytest.raises(HTTPException) as exc:
        ApplicationRepository(db_session).create_for_job(
            job, ApplicationCreate(candidate_id=candidate.id)
        )
    assert exc.value.status_code == 400


def test_duplicate_application_conflict(db_session) -> None:
    org = OrganizationRepository(db_session).create(
        OrganizationCreate(name="Dup Co", slug="dup-co")
    )
    job = JobRepository(db_session).create(org.id, JobCreate(title="Role", description=""))
    candidate = CandidateRepository(db_session).create(
        org.id, CandidateCreate(full_name="A", email="a@example.com")
    )
    ApplicationRepository(db_session).create_for_job(
        job, ApplicationCreate(candidate_id=candidate.id)
    )
    with pytest.raises(HTTPException) as exc:
        ApplicationRepository(db_session).create_for_job(
            job, ApplicationCreate(candidate_id=candidate.id)
        )
    assert exc.value.status_code == 409


def test_missing_entities_return_none(db_session) -> None:
    missing = uuid.uuid4()
    assert OrganizationRepository(db_session).get(missing) is None
    assert JobRepository(db_session).get(missing) is None
    assert CandidateRepository(db_session).get(missing) is None
