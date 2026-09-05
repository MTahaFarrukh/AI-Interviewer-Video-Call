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
    jobs,
    organizations,
)
from core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="FirstRound SaaS API",
    version="0.1.0",
    description=(
        "Phase 1 product API. Legacy LiveKit/Gemini interview engine remains "
        "available via CLI and token_server; this API does not replace it yet."
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


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "firstround-saas-api",
        "docs": "/docs",
        "health": "/health",
    }
