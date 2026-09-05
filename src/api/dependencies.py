"""Shared FastAPI dependencies."""

from __future__ import annotations

from auth.placeholders import AuthContext, get_current_organization, get_current_user
from core.database import get_db

__all__ = [
    "AuthContext",
    "get_current_organization",
    "get_current_user",
    "get_db",
]
