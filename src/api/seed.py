"""Development seed: Northwind Labs → Junior AI Engineer → demo candidate → interview."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy import select

from auth.placeholders import ensure_dev_user
from core.database import SessionLocal, engine
from core.enums import ApplicationStatus, InterviewStatus, JobStatus, MemberRole, QuestionPlanStatus
from core.settings import get_settings
from models import (  # noqa: F401 — register metadata
    Application,
    Candidate,
    Interview,
    Job,
    Organization,
    OrganizationMember,
    Question,
    QuestionPlan,
    User,
)
from core.database import Base
from repositories.question_plans import QuestionPlanRepository


DEMO_PLAN = {
    "questions": [
        {
            "id": "q1",
            "position": 1,
            "question": "Walk me through a RAG pipeline you have shipped end to end.",
            "competency": "Technical competence",
            "difficulty": "medium",
            "rationale": "JD requires RAG experience",
            "source": "jd",
        },
        {
            "id": "q2",
            "position": 2,
            "question": "How do you evaluate retrieval quality before changing prompts?",
            "competency": "Problem solving",
            "difficulty": "medium",
            "rationale": "Debugging discipline",
            "source": "jd",
        },
    ],
    "approved_by_human": False,
    "approval_status": "generated",
}


def seed() -> None:
    settings = get_settings()
    print(f"Using DATABASE_URL={settings.database_url}")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = ensure_dev_user(db)
        org = db.scalar(select(Organization).where(Organization.slug == "northwind-labs"))
        if org is None:
            org = Organization(name="Northwind Labs", slug="northwind-labs")
            db.add(org)
            db.flush()
            db.add(
                OrganizationMember(
                    organization_id=org.id,
                    user_id=user.id,
                    role=MemberRole.owner,
                )
            )
            db.commit()
            db.refresh(org)
            print(f"Created organization {org.id}")
        else:
            print(f"Organization exists {org.id}")

        job = db.scalar(
            select(Job).where(
                Job.organization_id == org.id,
                Job.title == "Junior AI Engineer",
            )
        )
        if job is None:
            job = Job(
                organization_id=org.id,
                title="Junior AI Engineer",
                department="AI Platform",
                location="Karachi (remote-friendly)",
                employment_type="full_time",
                description=(
                    "Help build internal assistants and retrieval-augmented tools "
                    "using Python and LangGraph/LangChain."
                ),
                status=JobStatus.active,
                created_by_user_id=user.id,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            print(f"Created job {job.id}")
        else:
            print(f"Job exists {job.id}")

        candidate = db.scalar(
            select(Candidate).where(
                Candidate.organization_id == org.id,
                Candidate.email == "alex.candidate@example.com",
            )
        )
        if candidate is None:
            candidate = Candidate(
                organization_id=org.id,
                full_name="Alex Candidate",
                email="alex.candidate@example.com",
                github_url="https://github.com/example-candidate",
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            print(f"Created candidate {candidate.id}")
        else:
            print(f"Candidate exists {candidate.id}")

        application = db.scalar(
            select(Application).where(
                Application.job_id == job.id,
                Application.candidate_id == candidate.id,
            )
        )
        if application is None:
            application = Application(
                organization_id=org.id,
                job_id=job.id,
                candidate_id=candidate.id,
                status=ApplicationStatus.interview_ready,
            )
            db.add(application)
            db.commit()
            db.refresh(application)
            print(f"Created application {application.id}")
        else:
            print(f"Application exists {application.id}")

        interview = db.scalar(
            select(Interview).where(Interview.application_id == application.id)
        )
        if interview is None:
            interview = Interview(
                organization_id=org.id,
                application_id=application.id,
                status=InterviewStatus.prepared,
            )
            db.add(interview)
            db.commit()
            db.refresh(interview)
            print(f"Created interview {interview.id}")
        else:
            print(f"Interview exists {interview.id}")

        plan_repo = QuestionPlanRepository(db)
        if plan_repo.get_latest_for_interview(interview.id) is None:
            plan_repo.save_plan_dict(
                interview,
                DEMO_PLAN,
                status=QuestionPlanStatus.generated,
                source="seed",
            )
            print("Seeded sample question plan")
        else:
            print("Question plan already present")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
