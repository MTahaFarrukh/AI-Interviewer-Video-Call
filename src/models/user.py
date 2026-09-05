from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    memberships: Mapped[list[OrganizationMember]] = relationship(
        "OrganizationMember", back_populates="user"
    )


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.organization_member import OrganizationMember
