from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from auth.placeholders import AuthContext, get_current_user
from core.database import get_db
from repositories.applications import ApplicationRepository
from repositories.interviews import InterviewRepository
from schemas.interview import (
    InterviewCreate,
    InterviewRead,
    InterviewUpdate,
    QuestionPlanNotReady,
    QuestionPlanRead,
)

router = APIRouter(tags=["interviews"])


@router.post(
    "/api/v1/applications/{application_id}/interviews",
    response_model=InterviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_interview(
    application_id: uuid.UUID,
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> InterviewRead:
    application = ApplicationRepository(db).get(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    interview = InterviewRepository(db).create_for_application(application, payload)
    return InterviewRead.model_validate(interview)


@router.get("/api/v1/interviews/{interview_id}", response_model=InterviewRead)
def get_interview(
    interview_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> InterviewRead:
    interview = InterviewRepository(db).get(interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return InterviewRead.model_validate(interview)


@router.patch("/api/v1/interviews/{interview_id}", response_model=InterviewRead)
def update_interview(
    interview_id: uuid.UUID,
    payload: InterviewUpdate,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> InterviewRead:
    repo = InterviewRepository(db)
    interview = repo.get(interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return InterviewRead.model_validate(repo.update(interview, payload))


@router.get(
    "/api/v1/interviews/{interview_id}/question-plan",
    response_model=QuestionPlanRead | QuestionPlanNotReady,
)
def get_interview_question_plan(
    interview_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    _auth: AuthContext = Depends(get_current_user),
) -> QuestionPlanRead | QuestionPlanNotReady:
    """Return DB-backed plan only — never the global file plan (wrong-candidate risk)."""
    repo = InterviewRepository(db)
    interview = repo.get(interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    plan = repo.get_latest_question_plan(interview_id)
    if plan is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return QuestionPlanNotReady(interview_id=interview_id)
    return QuestionPlanRead.model_validate(plan)
