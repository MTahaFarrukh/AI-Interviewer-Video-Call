"""Auth placeholders for Phase 1.

Real Supabase Auth / JWT verification belongs in Phase 2+.
Keep stub logic here — do not scatter fake-user checks across route modules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User


@dataclass(frozen=True)
class AuthContext:
    """Development auth context. Not security-sensitive until real auth lands."""

    user_id: uuid.UUID | None
    email: str
    full_name: str
    organization_id: uuid.UUID | None = None
    is_authenticated: bool = False


DEV_USER_EMAIL = "dev@firstround.local"


def get_current_user(db: Session = Depends(get_db)) -> AuthContext:
    """Placeholder dependency.

    Returns an unauthenticated development context. Later this will validate
    Supabase/JWT credentials and load the mapped User row.
    """
    _ = db
    return AuthContext(
        user_id=None,
        email=DEV_USER_EMAIL,
        full_name="Development User",
        organization_id=None,
        is_authenticated=False,
    )


def get_current_organization(
    auth: AuthContext = Depends(get_current_user),
) -> uuid.UUID | None:
    """Placeholder organization resolver.

    Routes that need tenancy should still take organization_id from the path
    and validate relationships in repositories. This hook is for future middleware.
    """
    return auth.organization_id


def ensure_dev_user(db: Session) -> User:
    """Create/fetch a local development user for seed scripts only."""
    from sqlalchemy import select

    user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is not None:
        return user
    user = User(email=DEV_USER_EMAIL, full_name="Development User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
