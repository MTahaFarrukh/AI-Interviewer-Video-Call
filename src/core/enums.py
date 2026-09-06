"""Shared enums for SaaS domain models."""

from __future__ import annotations

import enum


class MemberRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    recruiter = "recruiter"
    viewer = "viewer"


class JobStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"
    archived = "archived"


class ApplicationStatus(str, enum.Enum):
    invited = "invited"
    pending = "pending"
    interview_ready = "interview_ready"
    interviewing = "interviewing"
    completed = "completed"
    rejected = "rejected"
    hired = "hired"


class InterviewStatus(str, enum.Enum):
    draft = "draft"
    prepared = "prepared"
    ready = "ready"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class QuestionPlanStatus(str, enum.Enum):
    generated = "generated"
    review = "review"
    approved = "approved"
    superseded = "superseded"


class InviteStatus(str, enum.Enum):
    pending = "pending"
    opened = "opened"
    accepted = "accepted"
    completed = "completed"
    expired = "expired"
    revoked = "revoked"
