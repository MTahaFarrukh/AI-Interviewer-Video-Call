from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        connected = True
    except Exception:
        connected = False
    return {
        "status": "ok" if connected else "degraded",
        "database": "connected" if connected else "unavailable",
    }
