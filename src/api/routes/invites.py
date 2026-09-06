from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from auth.placeholders import AuthContext, get_current_user
from core.database import get_db
from models.interview import Interview
from repositories.interviews import InterviewRepository
from schemas.invite import (
    ConsentAcceptRequest,
    InviteCreatedResponse,
    InviteCreateRequest,
    InviteRead,
    PublicInviteRead,
    SessionStartResponse,
)
from services.invite_service import InterviewInviteService

router = APIRouter(tags=["invites"])


def _get_interview_or_404(db: Session, interview_id: uuid.UUID) -> Interview:
    interview = InterviewRepository(db).get(interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return interview


def _assert_recruiter_org_access(
    interview: Interview,
    *,
    organization_id_header: str | None,
    auth: AuthContext,
) -> None:
    """Lightweight tenancy guard for recruiter invite endpoints.

    When an organization scope is supplied (header or auth context), the interview
    must belong to that org. Missing scope remains allowed under Phase 1 placeholder auth.
    """
    scoped: uuid.UUID | None = auth.organization_id
    if organization_id_header:
        try:
            scoped = uuid.UUID(organization_id_header)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Organization-Id header",
            ) from exc
    if scoped is not None and interview.organization_id != scoped:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")


@router.post(
    "/api/v1/interviews/{interview_id}/invite",
    response_model=InviteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_interview_invite(
    interview_id: uuid.UUID,
    payload: InviteCreateRequest | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> InviteCreatedResponse:
    interview = _get_interview_or_404(db, interview_id)
    _assert_recruiter_org_access(
        interview, organization_id_header=x_organization_id, auth=auth
    )
    body = payload or InviteCreateRequest()
    result = InterviewInviteService(db).create_invite(
        interview_id, ttl_hours=body.ttl_hours
    )
    return InviteCreatedResponse(
        invite=InviteRead.model_validate(result.invite),
        invite_url_path=result.invite_url_path,
        raw_token=result.raw_token,
    )


@router.get(
    "/api/v1/interviews/{interview_id}/invite",
    response_model=InviteRead,
)
def get_interview_invite(
    interview_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> InviteRead:
    interview = _get_interview_or_404(db, interview_id)
    _assert_recruiter_org_access(
        interview, organization_id_header=x_organization_id, auth=auth
    )
    invite = InterviewInviteService(db).get_latest_invite(interview_id)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    return InviteRead.model_validate(invite)


@router.post(
    "/api/v1/interviews/{interview_id}/invite/regenerate",
    response_model=InviteCreatedResponse,
)
def regenerate_interview_invite(
    interview_id: uuid.UUID,
    payload: InviteCreateRequest | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> InviteCreatedResponse:
    interview = _get_interview_or_404(db, interview_id)
    _assert_recruiter_org_access(
        interview, organization_id_header=x_organization_id, auth=auth
    )
    body = payload or InviteCreateRequest()
    result = InterviewInviteService(db).regenerate_invite(
        interview_id, ttl_hours=body.ttl_hours
    )
    return InviteCreatedResponse(
        invite=InviteRead.model_validate(result.invite),
        invite_url_path=result.invite_url_path,
        raw_token=result.raw_token,
    )


@router.post(
    "/api/v1/interviews/{interview_id}/invite/revoke",
    response_model=InviteRead,
)
def revoke_interview_invite(
    interview_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> InviteRead:
    interview = _get_interview_or_404(db, interview_id)
    _assert_recruiter_org_access(
        interview, organization_id_header=x_organization_id, auth=auth
    )
    invite = InterviewInviteService(db).revoke_invite(interview_id)
    return InviteRead.model_validate(invite)


@router.get(
    "/api/v1/public/interview-invites/{token}",
    response_model=PublicInviteRead,
)
def get_public_invite(token: str, db: Session = Depends(get_db)) -> PublicInviteRead:
    payload = InterviewInviteService(db).build_public_payload(token, mark_opened=True)
    return PublicInviteRead.model_validate(payload.__dict__)


@router.post(
    "/api/v1/public/interview-invites/{token}/consent",
    response_model=PublicInviteRead,
)
def accept_public_invite_consent(
    token: str,
    payload: ConsentAcceptRequest,
    db: Session = Depends(get_db),
) -> PublicInviteRead:
    if not payload.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent must be accepted to continue",
        )
    result = InterviewInviteService(db).accept_consent(token)
    return PublicInviteRead.model_validate(result.__dict__)


@router.post(
    "/api/v1/public/interview-invites/{token}/session",
    response_model=SessionStartResponse,
)
def start_public_invite_session(
    token: str, db: Session = Depends(get_db)
) -> SessionStartResponse:
    result = InterviewInviteService(db).start_session(token)
    return SessionStartResponse(
        room_name=result.room_name,
        participant_identity=result.participant_identity,
        livekit_url=result.livekit_url,
        token=result.token,
        interview_id=result.interview_id,
        expected_duration_seconds=result.expected_duration_seconds,
        questions_total=result.questions_total,
    )


@router.post(
    "/api/v1/public/interview-invites/{token}/complete",
    response_model=PublicInviteRead,
)
def complete_public_invite(
    token: str, db: Session = Depends(get_db)
) -> PublicInviteRead:
    result = InterviewInviteService(db).complete_from_token(token)
    return PublicInviteRead.model_validate(result.__dict__)
