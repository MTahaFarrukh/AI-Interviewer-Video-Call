# FirstRound — Backend Architecture (Phase 1)

**Status:** Phase 1 implemented  
**Date:** 2026-09-05

This document describes the SaaS API added alongside the existing LiveKit / Gemini interview engine. The engine is **not** rewritten; both stacks coexist.

---

## Coexistence model

```text
Legacy (unchanged happy path)
  prepare_interview.py  →  output/question_plan.json
  agent.py              →  LiveKit + Gemini Live + InterviewController
  token_server.py:8080  →  static frontend + LiveKit JWT
  InterviewStore SQLite →  live turns
  evaluate / scorecard / PDF / MCP

SaaS (new, optional)
  FastAPI :8000         →  orgs / jobs / candidates / applications / interviews
  SQLAlchemy + Alembic  →  PostgreSQL-compatible product DB (SQLite OK locally)
  PlanRepository        →  File (legacy) | Database (per-interview)
  LiveKitTokenService   →  shared mint logic (used by token_server)
  InterviewSessionStore →  adapter boundary over existing InterviewStore
```

The live agent still loads the **global file plan** via `plan_loader`. The API **never** silently falls back to that file for `GET /interviews/{id}/question-plan` (wrong-candidate risk).

---

## FastAPI layout

```text
src/
  api/
    main.py              # app entry
    dependencies.py      # shared deps
    seed.py              # Northwind demo seed
    routes/
      health.py
      organizations.py
      jobs.py
      candidates.py
      applications.py
      interviews.py
  auth/
    placeholders.py      # get_current_user / get_current_organization stubs
  core/
    settings.py          # DATABASE_URL, APP_ENV, future Supabase/LiveKit keys
    database.py          # engine, SessionLocal, Base
    enums.py
  models/                # SQLAlchemy ORM
  schemas/               # Pydantic request/response
  repositories/          # data access
  services/
    plan_repository.py
    livekit_token.py
    interview_session_store.py
  config.py              # LEGACY engine config (kept)
  token_server.py        # LEGACY HTTP :8080 (uses LiveKitTokenService)
  agent.py               # LEGACY protected engine
```

Run API (from repo root):

```powershell
$env:PYTHONPATH="src"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Additional list endpoints added for the Phase 2 recruiter UI:

- `GET /api/v1/organizations/{organization_id}/interviews`
- `GET /api/v1/organizations/{organization_id}/applications`
- `GET /api/v1/candidates/{candidate_id}/applications`

---

## Database models

| Table | Purpose |
|-------|---------|
| `users` | Future auth mapping |
| `organizations` | Workspace / tenant |
| `organization_members` | user ↔ org + role |
| `jobs` | Role openings |
| `candidates` | Org-scoped people |
| `applications` | candidate ↔ job |
| `interviews` | Session product entity |
| `question_plans` | Per-interview plan versions |
| `questions` | Ordered questions for a plan |

### Relationships

`Organization` 1—* `Job` / `Candidate` / `OrganizationMember`  
`Job` + `Candidate` → `Application` (unique pair)  
`Application` 1—* `Interview`  
`Interview` 1—* `QuestionPlan` 1—* `Question`

Multi-tenancy: applications reject cross-org job/candidate pairs. Auth middleware is still a placeholder; path `organization_id` + FK checks are the Phase 1 boundary.

Migrations: Alembic (`alembic/versions/…_phase1_saas_initial.py`).

---

## Repository responsibilities

| Repository | Role |
|------------|------|
| `OrganizationRepository` | Create/list/get orgs |
| `JobRepository` | Org jobs + patch/status |
| `CandidateRepository` | Org candidates |
| `ApplicationRepository` | Create with tenancy checks |
| `InterviewRepository` | Create/get/patch + latest plan |
| `QuestionPlanRepository` | Persist engine-shaped plan dicts |

---

## Service boundaries

### PlanRepository

- **`FilePlanRepository`** — wraps `output/question_plan.json` (legacy compatibility).
- **`DatabasePlanRepository`** — stores/loads plans by interview UUID.

Default live path remains file-based until a later phase binds `agent.py` to DB plans.

### LiveKitTokenService

Single mint implementation in `services/livekit_token.py`.  
`token_server._mint_token` delegates here — no duplicated JWT logic.

### InterviewSessionStore

Protocol + `SqliteInterviewSessionStore` wrapping `realtime.store.InterviewStore`.  
Agent still calls `InterviewStore` directly; the adapter documents the future cutover.

### Auth placeholders

`auth.placeholders.get_current_user` / `get_current_organization` — unauthenticated dev context. Do not scatter fake-user logic in routes.

---

## Migration path: global JSON → per-interview DB

1. **Now:** dual systems; file remains source of truth for live engine.  
2. **Next:** prep/HITL write DB plans per `interview_id` while still exporting file for local demos.  
3. **Later:** agent loads `DatabasePlanRepository.get_plan_for_interview(id)` from room metadata.  
4. **Finally:** retire global plan for production; keep file only for offline fixtures/tests.

---

## Seed

```powershell
$env:PYTHONPATH="src"
python src\api\seed.py
```

Creates Northwind Labs → Junior AI Engineer → Alex Candidate → application → prepared interview + sample plan.
