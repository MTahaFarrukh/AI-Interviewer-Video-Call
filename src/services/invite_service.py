"""Interview invite service — secure tokens, hashing, lifecycle transitions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.enums import ApplicationStatus, InterviewStatus, InviteStatus
from models.application import Application
from models.candidate import Candidate
from models.interview import Interview
from models.interview_invite import InterviewInvite
from models.job import Job
from models.organization import Organization
from services.livekit_token import get_livekit_token_service

DEFAULT_INVITE_TTL_HOURS = 72
ACTIVE_INVITE_STATUSES = frozenset(
    {InviteStatus.pending, InviteStatus.opened, InviteStatus.accepted}
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_invite_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_invite_token() -> str:
    # 32 bytes → 43 url-safe chars; opaque and non-sequential
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class InviteCreationResult:
    invite: InterviewInvite
    raw_token: str
    invite_url_path: str


@dataclass(frozen=True)
class PublicInvitePayload:
    invite_status: InviteStatus
    can_begin_setup: bool
    can_enter_room: bool
    expires_at: datetime
    candidate_name: str
    organization_name: str
    job_title: str
    expected_duration_seconds: int
    interview_status: InterviewStatus
    consent_accepted: bool
    message: str | None = None


@dataclass(frozen=True)
class SessionStartResult:
    room_name: str
    participant_identity: str
    livekit_url: str
    token: str
    interview_id: str
    expected_duration_seconds: int
    questions_total: int | None


class InterviewInviteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_interview(self, interview_id: uuid.UUID) -> Interview:
        interview = self.db.get(Interview, interview_id)
        if interview is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
        return interview

    def get_active_invite(self, interview_id: uuid.UUID) -> InterviewInvite | None:
        stmt = (
            select(InterviewInvite)
            .where(
                InterviewInvite.interview_id == interview_id,
                InterviewInvite.status.in_(tuple(ACTIVE_INVITE_STATUSES)),
            )
            .order_by(InterviewInvite.created_at.desc())
            .limit(1)
        )
        invite = self.db.scalar(stmt)
        if invite is None:
            return None
        return self._refresh_expiry(invite)

    def get_latest_invite(self, interview_id: uuid.UUID) -> InterviewInvite | None:
        stmt = (
            select(InterviewInvite)
            .where(InterviewInvite.interview_id == interview_id)
            .order_by(InterviewInvite.created_at.desc())
            .limit(1)
        )
        invite = self.db.scalar(stmt)
        if invite is None:
            return None
        return self._refresh_expiry(invite)

    def create_invite(
        self,
        interview_id: uuid.UUID,
        *,
        ttl_hours: int = DEFAULT_INVITE_TTL_HOURS,
        frontend_base_path: str = "/interview",
    ) -> InviteCreationResult:
        interview = self._get_interview(interview_id)
        if interview.status in {InterviewStatus.completed, InterviewStatus.cancelled}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot invite for a completed or cancelled interview",
            )
        if interview.status == InterviewStatus.in_progress:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview is already in progress",
            )

        existing = self.get_active_invite(interview_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active invite already exists; regenerate or revoke first",
            )

        raw = generate_invite_token()
        invite = InterviewInvite(
            interview_id=interview.id,
            token_hash=hash_invite_token(raw),
            status=InviteStatus.pending,
            expires_at=utcnow() + timedelta(hours=ttl_hours),
        )
        self.db.add(invite)

        if interview.status in {InterviewStatus.draft, InterviewStatus.prepared}:
            interview.status = InterviewStatus.ready
            self.db.add(interview)

        app = self.db.get(Application, interview.application_id)
        if app is not None and app.status in {
            ApplicationStatus.pending,
            ApplicationStatus.interview_ready,
        }:
            app.status = ApplicationStatus.invited
            self.db.add(app)

        self.db.commit()
        self.db.refresh(invite)
        return InviteCreationResult(
            invite=invite,
            raw_token=raw,
            invite_url_path=f"{frontend_base_path.rstrip('/')}/{raw}",
        )

    def regenerate_invite(
        self,
        interview_id: uuid.UUID,
        *,
        ttl_hours: int = DEFAULT_INVITE_TTL_HOURS,
    ) -> InviteCreationResult:
        active = self.get_active_invite(interview_id)
        if active is not None:
            active.status = InviteStatus.revoked
            self.db.add(active)
            self.db.flush()
        return self.create_invite(interview_id, ttl_hours=ttl_hours)

    def revoke_invite(self, interview_id: uuid.UUID) -> InterviewInvite:
        invite = self.get_active_invite(interview_id)
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active invite")
        invite.status = InviteStatus.revoked
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)
        return invite

    def _refresh_expiry(self, invite: InterviewInvite) -> InterviewInvite:
        if invite.status in ACTIVE_INVITE_STATUSES and as_utc(invite.expires_at) <= utcnow():
            invite.status = InviteStatus.expired
            self.db.add(invite)
            self.db.commit()
            self.db.refresh(invite)
        return invite

    def resolve_by_raw_token(self, raw_token: str) -> InterviewInvite:
        token = (raw_token or "").strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        digest = hash_invite_token(token)
        invite = self.db.scalar(
            select(InterviewInvite).where(InterviewInvite.token_hash == digest)
        )
        if invite is None:
            # Constant-time compare against a dummy digest to reduce timing hints
            hmac.compare_digest(digest, hash_invite_token("invalid-token-placeholder"))
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        return self._refresh_expiry(invite)

    def _load_context(self, invite: InterviewInvite) -> tuple[Interview, Application, Candidate, Job, Organization]:
        interview = self.db.get(Interview, invite.interview_id)
        if interview is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
        application = self.db.get(Application, interview.application_id)
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        candidate = self.db.get(Candidate, application.candidate_id)
        job = self.db.get(Job, application.job_id)
        organization = self.db.get(Organization, interview.organization_id)
        if candidate is None or job is None or organization is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite context missing")
        return interview, application, candidate, job, organization

    def build_public_payload(self, raw_token: str, *, mark_opened: bool = True) -> PublicInvitePayload:
        invite = self.resolve_by_raw_token(raw_token)
        interview, _application, candidate, job, organization = self._load_context(invite)

        message: str | None = None
        can_begin = False
        can_enter = False

        if invite.status == InviteStatus.revoked:
            message = "This invitation has been revoked."
        elif invite.status == InviteStatus.expired:
            message = "This invitation has expired."
        elif invite.status == InviteStatus.completed or interview.status == InterviewStatus.completed:
            message = "This interview has already been completed."
        elif interview.status in {InterviewStatus.cancelled, InterviewStatus.failed}:
            message = "This interview is no longer available."
        elif interview.status == InterviewStatus.in_progress and invite.status != InviteStatus.accepted:
            message = "This interview is already in progress in another session."
        else:
            can_begin = True
            can_enter = invite.consent_accepted_at is not None
            if mark_opened and invite.status == InviteStatus.pending:
                invite.status = InviteStatus.opened
                invite.opened_at = utcnow()
                self.db.add(invite)
                self.db.commit()
                self.db.refresh(invite)

        return PublicInvitePayload(
            invite_status=invite.status,
            can_begin_setup=can_begin,
            can_enter_room=can_enter and can_begin,
            expires_at=invite.expires_at,
            candidate_name=candidate.full_name,
            organization_name=organization.name,
            job_title=job.title,
            expected_duration_seconds=interview.expected_duration_seconds,
            interview_status=interview.status,
            consent_accepted=invite.consent_accepted_at is not None,
            message=message,
        )

    def accept_consent(self, raw_token: str) -> PublicInvitePayload:
        invite = self.resolve_by_raw_token(raw_token)
        if invite.status not in {InviteStatus.pending, InviteStatus.opened, InviteStatus.accepted}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invite cannot accept consent in its current state",
            )
        if invite.consent_accepted_at is None:
            invite.consent_accepted_at = utcnow()
        if invite.status in {InviteStatus.pending, InviteStatus.opened}:
            invite.status = InviteStatus.accepted
            invite.accepted_at = utcnow()
            if invite.opened_at is None:
                invite.opened_at = invite.accepted_at
        self.db.add(invite)
        self.db.commit()
        return self.build_public_payload(raw_token, mark_opened=False)

    def ensure_room_name(self, interview: Interview) -> str:
        if interview.livekit_room_name:
            return interview.livekit_room_name
        room = f"interview_{interview.id.hex}"
        interview.livekit_room_name = room
        self.db.add(interview)
        self.db.flush()
        return room

    def start_session(self, raw_token: str) -> SessionStartResult:
        invite = self.resolve_by_raw_token(raw_token)
        if invite.status in {InviteStatus.revoked, InviteStatus.expired, InviteStatus.completed}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invite is not available for joining",
            )
        if invite.consent_accepted_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consent is required before starting the interview",
            )

        interview, application, candidate, _job, _org = self._load_context(invite)

        if interview.status == InterviewStatus.completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview already completed",
            )
        if interview.status == InterviewStatus.in_progress:
            # Allow reconnect for the accepted invite that owns the session
            if invite.status != InviteStatus.accepted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Interview is already in progress",
                )
        if interview.status in {InterviewStatus.cancelled, InterviewStatus.failed}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Interview is unavailable",
            )

        if invite.status != InviteStatus.accepted:
            invite.status = InviteStatus.accepted
            invite.accepted_at = utcnow()
            self.db.add(invite)

        room = self.ensure_room_name(interview)
        if interview.status != InterviewStatus.in_progress:
            interview.status = InterviewStatus.in_progress
            if interview.started_at is None:
                interview.started_at = utcnow()
            self.db.add(interview)

        application.status = ApplicationStatus.interviewing
        self.db.add(application)
        self.db.commit()
        self.db.refresh(interview)

        identity = f"candidate-{interview.id.hex[:12]}"
        join = get_livekit_token_service().mint_join_token(
            candidate.full_name,
            room=room,
            identity=identity,
        )

        questions_total = None
        from models.question import Question
        from models.question_plan import QuestionPlan
        from sqlalchemy import func

        latest_plan = self.db.scalar(
            select(QuestionPlan)
            .where(QuestionPlan.interview_id == interview.id)
            .order_by(QuestionPlan.version.desc())
            .limit(1)
        )
        if latest_plan is not None:
            questions_total = int(
                self.db.scalar(
                    select(func.count())
                    .select_from(Question)
                    .where(Question.question_plan_id == latest_plan.id)
                )
                or 0
            )

        return SessionStartResult(
            room_name=join.room,
            participant_identity=join.identity,
            livekit_url=join.url,
            token=join.token,
            interview_id=str(interview.id),
            expected_duration_seconds=interview.expected_duration_seconds,
            questions_total=questions_total,
        )

    def complete_from_token(self, raw_token: str) -> PublicInvitePayload:
        invite = self.resolve_by_raw_token(raw_token)
        interview, application, *_rest = self._load_context(invite)

        now = utcnow()
        invite.status = InviteStatus.completed
        invite.completed_at = now
        self.db.add(invite)

        if interview.status != InterviewStatus.completed:
            interview.status = InterviewStatus.completed
            interview.completed_at = now
            if interview.started_at is not None:
                interview.duration_seconds = int(
                    max(0, (now - as_utc(interview.started_at)).total_seconds())
                )
            self.db.add(interview)

        if application.status != ApplicationStatus.completed:
            application.status = ApplicationStatus.completed
            self.db.add(application)

        self.db.commit()
        return self.build_public_payload(raw_token, mark_opened=False)
