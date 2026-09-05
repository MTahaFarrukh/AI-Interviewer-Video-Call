from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from core.database import Base
from core.enums import QuestionPlanStatus
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.interview import Interview
    from models.question import Question


class QuestionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_plans"
    __table_args__ = (
        UniqueConstraint("interview_id", "version", name="uq_question_plan_interview_version"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[QuestionPlanStatus] = mapped_column(
        Enum(QuestionPlanStatus, name="question_plan_status", native_enum=False, length=32),
        nullable=False,
        default=QuestionPlanStatus.generated,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recruiter_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    interview: Mapped[Interview] = relationship("Interview", back_populates="question_plans")
    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="question_plan",
        cascade="all, delete-orphan",
        order_by="Question.position",
    )
