from __future__ import annotations

import uuid

from schemas.candidate import CandidateCreate
from schemas.job import JobCreate
from schemas.organization import OrganizationCreate
from schemas.application import ApplicationCreate
from schemas.interview import InterviewCreate


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_organization_and_job_api(client) -> None:
    create = client.post(
        "/api/v1/organizations",
        json={"name": "Northwind Labs", "slug": "northwind-labs"},
    )
    assert create.status_code == 201
    org_id = create.json()["id"]

    listed = client.get("/api/v1/organizations")
    assert listed.status_code == 200
    assert any(item["id"] == org_id for item in listed.json())

    got = client.get(f"/api/v1/organizations/{org_id}")
    assert got.status_code == 200
    assert got.json()["slug"] == "northwind-labs"

    job = client.post(
        f"/api/v1/organizations/{org_id}/jobs",
        json={
            "title": "Junior AI Engineer",
            "description": "Build RAG tools",
            "status": "active",
        },
    )
    assert job.status_code == 201
    job_id = job.json()["id"]

    patched = client.patch(f"/api/v1/jobs/{job_id}", json={"status": "archived"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "archived"


def test_candidate_application_interview_and_plan_endpoint(client) -> None:
    org = client.post(
        "/api/v1/organizations", json={"name": "Demo Org", "slug": "demo-org"}
    ).json()
    org_id = org["id"]
    job = client.post(
        f"/api/v1/organizations/{org_id}/jobs",
        json={"title": "Engineer", "description": "x", "status": "active"},
    ).json()
    candidate = client.post(
        f"/api/v1/organizations/{org_id}/candidates",
        json={"full_name": "Alex Candidate", "email": "alex.candidate@example.com"},
    ).json()
    application = client.post(
        f"/api/v1/jobs/{job['id']}/applications",
        json={"candidate_id": candidate["id"], "status": "pending"},
    ).json()
    interview = client.post(
        f"/api/v1/applications/{application['id']}/interviews",
        json={"status": "prepared"},
    ).json()

    missing_plan = client.get(f"/api/v1/interviews/{interview['id']}/question-plan")
    assert missing_plan.status_code == 404
    assert missing_plan.json()["status"] == "not_ready"

    bad = client.get(f"/api/v1/interviews/{uuid.uuid4()}")
    assert bad.status_code == 404
    assert bad.json()["detail"] == "Interview not found"


def test_validation_rejects_bad_org_slug(client) -> None:
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Bad", "slug": "NOT VALID"},
    )
    assert response.status_code == 422
