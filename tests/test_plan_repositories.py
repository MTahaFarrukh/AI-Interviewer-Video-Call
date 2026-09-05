from __future__ import annotations

import json
from pathlib import Path

from core.enums import QuestionPlanStatus
from repositories.interviews import InterviewRepository
from repositories.jobs import JobRepository
from repositories.organizations import OrganizationRepository
from repositories.candidates import CandidateRepository
from repositories.applications import ApplicationRepository
from repositories.question_plans import QuestionPlanRepository
from schemas.application import ApplicationCreate
from schemas.candidate import CandidateCreate
from schemas.interview import InterviewCreate
from schemas.job import JobCreate
from schemas.organization import OrganizationCreate
from services.plan_repository import DatabasePlanRepository, FilePlanRepository


SAMPLE_PLAN = {
    "questions": [
        {
            "id": "q1",
            "question": "Explain embeddings.",
            "competency": "Technical competence",
            "difficulty": "easy",
            "source": "jd",
        }
    ],
    "approved_by_human": True,
    "approval_status": "approved",
}


def _interview(db_session):
    org = OrganizationRepository(db_session).create(
        OrganizationCreate(name="Plan Co", slug="plan-co")
    )
    job = JobRepository(db_session).create(org.id, JobCreate(title="Role", description=""))
    candidate = CandidateRepository(db_session).create(
        org.id, CandidateCreate(full_name="Pat", email="pat@example.com")
    )
    application = ApplicationRepository(db_session).create_for_job(
        job, ApplicationCreate(candidate_id=candidate.id)
    )
    return InterviewRepository(db_session).create_for_application(
        application, InterviewCreate()
    )


def test_file_plan_repository_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "question_plan.json"
    repo = FilePlanRepository(path)
    saved = repo.save_plan_for_interview("ignored", SAMPLE_PLAN)
    assert saved["questions"][0]["question"] == "Explain embeddings."
    loaded = repo.get_plan_for_interview("anything")
    assert loaded is not None
    assert loaded["approval_status"] == "approved"
    assert json.loads(path.read_text(encoding="utf-8"))["questions"]


def test_database_plan_repository_roundtrip(db_session) -> None:
    interview = _interview(db_session)
    repo = DatabasePlanRepository(db_session)
    saved = repo.save_plan_for_interview(interview.id, SAMPLE_PLAN)
    assert saved["approved_by_human"] is True
    assert len(saved["questions"]) == 1
    loaded = repo.get_plan_for_interview(interview.id)
    assert loaded is not None
    assert loaded["questions"][0]["text"] == "Explain embeddings."
    plan_row = QuestionPlanRepository(db_session).get_latest_for_interview(interview.id)
    assert plan_row is not None
    assert plan_row.status == QuestionPlanStatus.approved
    assert plan_row.questions[0].position == 1
