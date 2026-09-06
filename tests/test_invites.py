from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from core.enums import InterviewStatus, InviteStatus, JobStatus
from repositories.applications import ApplicationRepository
from repositories.candidates import CandidateRepository
from repositories.interviews import InterviewRepository
from repositories.jobs import JobRepository
from repositories.organizations import OrganizationRepository
from schemas.application import ApplicationCreate
from schemas.candidate import CandidateCreate
from schemas.interview import InterviewCreate
from schemas.job import JobCreate
from schemas.organization import OrganizationCreate
from services.invite_service import InterviewInviteService, hash_invite_token


def _seed_interview(db_session):
    org = OrganizationRepository(db_session).create(
        OrganizationCreate(name="Invite Co", slug="invite-co")
    )
    job = JobRepository(db_session).create(
        org.id,
        JobCreate(
            title="Engineer",
            description="Build things",
            status=JobStatus.active,
        ),
    )
    candidate = CandidateRepository(db_session).create(
        org.id,
        CandidateCreate(full_name="Alex Candidate", email="alex.invite@example.com"),
    )
    application = ApplicationRepository(db_session).create_for_job(
        job, ApplicationCreate(candidate_id=candidate.id)
    )
    interview = InterviewRepository(db_session).create_for_application(
        application, InterviewCreate(status=InterviewStatus.prepared)
    )
    return org, interview, candidate


def test_invite_hash_not_raw_token(db_session) -> None:
    _org, interview, _candidate = _seed_interview(db_session)
    service = InterviewInviteService(db_session)
    created = service.create_invite(interview.id)
    assert created.raw_token
    assert created.invite.token_hash == hash_invite_token(created.raw_token)
    assert created.raw_token not in created.invite.token_hash
    assert hashlib.sha256(created.raw_token.encode()).hexdigest() == created.invite.token_hash


def test_invite_lookup_expiry_revoke_regenerate(db_session) -> None:
    _org, interview, _candidate = _seed_interview(db_session)
    service = InterviewInviteService(db_session)
    created = service.create_invite(interview.id, ttl_hours=1)
    public = service.build_public_payload(created.raw_token)
    assert public.can_begin_setup is True
    assert public.candidate_name == "Alex Candidate"
    assert "score" not in public.__dict__

    invite = service.get_active_invite(interview.id)
    assert invite is not None
    invite.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.add(invite)
    db_session.commit()
    expired = service.build_public_payload(created.raw_token)
    assert expired.invite_status == InviteStatus.expired
    assert expired.can_begin_setup is False

    regenerated = service.regenerate_invite(interview.id)
    assert regenerated.raw_token != created.raw_token
    revoked = service.revoke_invite(interview.id)
    assert revoked.status == InviteStatus.revoked


def test_completed_invite_rejects_session(db_session, monkeypatch) -> None:
    _org, interview, _candidate = _seed_interview(db_session)
    service = InterviewInviteService(db_session)
    created = service.create_invite(interview.id)
    service.accept_consent(created.raw_token)
    service.complete_from_token(created.raw_token)

    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as exc:
        service.start_session(created.raw_token)
    assert exc.value.status_code == 409


def test_public_invite_and_session_endpoints(client, monkeypatch) -> None:
    org = client.post(
        "/api/v1/organizations", json={"name": "Pub Co", "slug": "pub-co"}
    ).json()
    job = client.post(
        f"/api/v1/organizations/{org['id']}/jobs",
        json={"title": "Role", "description": "x", "status": "active"},
    ).json()
    candidate = client.post(
        f"/api/v1/organizations/{org['id']}/candidates",
        json={"full_name": "Sam Example", "email": "sam.pub@example.com"},
    ).json()
    application = client.post(
        f"/api/v1/jobs/{job['id']}/applications",
        json={"candidate_id": candidate["id"]},
    ).json()
    interview = client.post(
        f"/api/v1/applications/{application['id']}/interviews",
        json={"status": "prepared"},
    ).json()

    created = client.post(f"/api/v1/interviews/{interview['id']}/invite").json()
    token = created["raw_token"]
    assert "token_hash" not in created["invite"]
    assert created["invite_url_path"].endswith(token)

    public = client.get(f"/api/v1/public/interview-invites/{token}")
    assert public.status_code == 200
    body = public.json()
    assert body["job_title"] == "Role"
    assert "organization_id" not in body
    assert body["can_begin_setup"] is True

    consent = client.post(
        f"/api/v1/public/interview-invites/{token}/consent",
        json={"accepted": True},
    )
    assert consent.status_code == 200
    assert consent.json()["consent_accepted"] is True

    class FakeJoin:
        token = "fake-livekit-jwt"
        url = "wss://example.livekit.cloud"
        room = f"interview_{interview['id'].replace('-', '')}"
        identity = "candidate-test"

    class FakeService:
        def mint_join_token(self, name, **kwargs):
            assert kwargs.get("room", "").startswith("interview_")
            return FakeJoin()

    monkeypatch.setattr(
        "services.invite_service.get_livekit_token_service",
        lambda: FakeService(),
    )

    session = client.post(f"/api/v1/public/interview-invites/{token}/session")
    assert session.status_code == 200
    payload = session.json()
    assert payload["token"] == "fake-livekit-jwt"
    assert payload["room_name"].startswith("interview_")

    # Room reuse on second start
    session2 = client.post(f"/api/v1/public/interview-invites/{token}/session")
    assert session2.status_code == 200
    assert session2.json()["room_name"] == payload["room_name"]

    got = client.get(f"/api/v1/interviews/{interview['id']}")
    assert got.json()["livekit_room_name"] == payload["room_name"]
    assert got.json()["status"] == "in_progress"


def test_cross_org_invite_access_denied(client) -> None:
    org_a = client.post(
        "/api/v1/organizations", json={"name": "Org A", "slug": "org-a-invite"}
    ).json()
    org_b = client.post(
        "/api/v1/organizations", json={"name": "Org B", "slug": "org-b-invite"}
    ).json()
    job = client.post(
        f"/api/v1/organizations/{org_a['id']}/jobs",
        json={"title": "Role", "description": "x", "status": "active"},
    ).json()
    candidate = client.post(
        f"/api/v1/organizations/{org_a['id']}/candidates",
        json={"full_name": "Cross Org", "email": "cross.org@example.com"},
    ).json()
    application = client.post(
        f"/api/v1/jobs/{job['id']}/applications",
        json={"candidate_id": candidate["id"]},
    ).json()
    interview = client.post(
        f"/api/v1/applications/{application['id']}/interviews",
        json={"status": "prepared"},
    ).json()

    denied = client.post(
        f"/api/v1/interviews/{interview['id']}/invite",
        headers={"X-Organization-Id": org_b["id"]},
    )
    assert denied.status_code == 404

    allowed = client.post(
        f"/api/v1/interviews/{interview['id']}/invite",
        headers={"X-Organization-Id": org_a["id"]},
    )
    assert allowed.status_code == 201
