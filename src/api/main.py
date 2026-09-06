"""FastAPI application entrypoint for the FirstRound SaaS API."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    applications,
    candidates,
    health,
    interviews,
    invites,
    jobs,
    organizations,
)
from core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="FirstRound SaaS API",
    version="0.2.0",
    description=(
        "SaaS product API. Legacy LiveKit/Gemini interview engine remains "
        "available via CLI and token_server; Phase 3 adds candidate invites/sessions."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(organizations.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(interviews.router)
app.include_router(invites.router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "firstround-saas-api",
        "docs": "/docs",
        "health": "/health",
    }
