# FirstRound — SaaS Upgrade Plan

**Status:** Phase 1 complete (API + DB foundation)  
**Date:** 2026-09-05  
**Public repo:** https://github.com/MTahaFarrukh/AI-Interviewer-Video-Call  
**Constraint:** preserve the working LiveKit + Gemini Live interview engine

See also: [`BACKEND_ARCHITECTURE.md`](BACKEND_ARCHITECTURE.md)

### Phase progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1 — Architecture & SaaS foundation | **Done** | FastAPI, SQLAlchemy, Alembic, CRUD APIs, PlanRepository, LiveKitTokenService, InterviewSessionStore adapter, seed, tests |
| 2 — Premium frontend shell | Not started | |
| 3 — Jobs/candidates/invites UI | Not started | |
| 4 — Candidate interview experience | Not started | |
| 5 — Bind engine to SaaS entities | Not started | Critical: remove global plan assumption for production |
| 6 — Simli avatar | Not started | |
| 7 — Analytics / reports polish | Not started | |
| 8 — Production hardening | Not started | |

---

## 1. Executive summary

FirstRound is a **working AI technical interviewer prototype** built for a course final. Prep, live voice interview, scoring, PDF, and MCP all exist and run from the terminal + a static browser room.

The SaaS goal is:

> A recruiter signs up, creates a job, invites a candidate, FirstRound conducts a realistic AI voice interview, and the recruiter receives an evidence-backed evaluation **without touching a terminal**.

**Strategy:** evolve around the interview engine. Add auth, multi-tenant data, APIs, and product UI as a **new shell**. Keep LiveKit / Gemini / `InterviewController` / evaluator as protected services behind clean boundaries. Introduce Simli later via an `AvatarProvider` abstraction. Do **not** rewrite the realtime brain to “clean up” architecture.

---

## 2. Current architecture map

### 2.1 High-level flow (today)

```text
CLI: prepare_interview.py
  → LangGraph prep (SqliteSaver) + HITL
  → output/question_plan.json (+ output/prep/*.json)

Terminals:
  agent.py start          ← LiveKit Agents worker + Gemini Live
  token_server.py :8080   ← static frontend + POST /token

Browser:
  frontend/               ← landing → setup → room (2D face) → complete

After:
  evaluate / scorecard / report.pdf
  mcp_server.py (stdio) ← Claude Desktop
```

There is **no FastAPI app today**. The only HTTP surface is `ThreadingHTTPServer` in `src/token_server.py`.

### 2.2 Frontend

| Path | Role |
|------|------|
| `frontend/index.html` | Single-page screens: landing, setup, interview, complete, partial |
| `frontend/app.js` | LiveKit client join, mic check, timer, progress via `interview_ui` data messages, 2D mouth from agent audio RMS |
| `frontend/styles.css` | Current visual system |
| `frontend/public/avatar.png` | Local interviewer portrait |

**Characteristics:** hardcoded Northwind Labs / Junior AI Engineer copy; join requires only a typed name; no auth; no invite token; no recruiter UI.

### 2.3 Backend / servers

| Component | Tech | Role |
|-----------|------|------|
| `src/token_server.py` | stdlib HTTP | Serve static files; mint LiveKit JWT; dispatch agent by name |
| `src/agent.py` | livekit-agents + Gemini RealtimeModel | Live interview session |
| `src/prepare_interview.py` | CLI | Run prep graph / HITL resume |
| `src/mcp_server.py` | FastMCP stdio | Recruiter tools (offline) |
| Offline CLIs | evaluate / report / grading artifacts | Post-interview outputs |

### 2.4 LangGraph prep pipeline

- **Entry:** `src/prepare_interview.py` → `src/graph.py`
- **Checkpointer:** `output/prep/langgraph.sqlite` (`SqliteSaver`)
- **Nodes (11):** ingest → parse resume/JD → profile → gap → GitHub extract/analyze → question plan → validate → HITL → finalize
- **Outputs:** `output/prep/*.json`, approved plan at `output/question_plan.json`
- **HITL:** `interrupt()` with approve / edit / reject via CLI flags

### 2.5 LiveKit + Gemini integration

- Room created implicitly via token (`firstround-<identity>`)
- Agent dispatched: `firstround-interviewer` (`AGENT_NAME`)
- Model: `gemini-2.5-flash-native-audio-preview-12-2025` via `google.realtime.RealtimeModel`
- Voice: `Puck`; input/output transcription enabled
- Barge-in: platform interruption + `[INTERRUPT]` logging
- UI sync: agent publishes JSON data packets `type: interview_ui`
- Plan gate: refuses start without approved plan on disk

### 2.6 Transcript persistence

- Hot path: `InterviewController` transcript list
- SQLite: `output/live/interview.sqlite` via `InterviewStore`
  - tables: `interviews`, `turns`
  - fields: candidate/role/company, phase, status, question index, follow-ups, elapsed, transcript JSON
- Also: `output/interview_transcript.json`
- Graded export: `output/transcript.json` (PDF schema)

### 2.7 Evaluator + reports

- Live labels: `src/realtime/evaluate.py` (shallow / strong / bluff / …)
- Offline eval: `src/realtime/evaluate_interview.py`
- Evidence-gated scorecard: `src/realtime/scorecard.py` (rejects scores without ≥12-char quote)
- PDF: `src/realtime/pdf_report.py` → `output/report.pdf`
- JSON/MD reports via `generate_report.py` / related modules

### 2.8 MCP

- `src/mcp_server.py` — tools such as `get_candidate`, `get_question_plan`, `save_score`, `get_scorecard`, `list_interviews`, plus transcript/status helpers
- **Not** on the audio path; secrets redacted
- Useful as a recruiter power-user surface; SaaS dashboard should not depend on Claude Desktop

### 2.9 Database / storage usage today

| Store | Purpose | SaaS fitness |
|-------|---------|--------------|
| `output/prep/langgraph.sqlite` | Prep graph checkpoints | Keep for prep workers / local; not multi-tenant product DB |
| `output/live/interview.sqlite` | Live interview + turns | Prototype session store; migrate meaning → Postgres |
| JSON files under `output/` | Plans, scorecards, PDFs | Replace as source of truth with DB + object storage |
| `inputs/` | Resume PDF, JD text | Become per-application uploads |
| Single `output/question_plan.json` | **Global** live plan | Critical SaaS blocker — one plan for whole machine |

### 2.10 Auth / tenancy / product shell

**Absent:** users, orgs, jobs, invites, sessions, billing hooks, multi-interview concurrency model, production deploy config, structured observability.

---

## 3. Protected components (do not rewrite)

These already work and define product value. Wrap them; do not replace unless a concrete bug or SaaS requirement forces a **minimal** change.

| Component | Why protected |
|-----------|----------------|
| `src/agent.py` LiveKit session + Gemini `RealtimeModel` wiring | Working realtime brain |
| Barge-in / turn logging / latency instrumentation | Spec-critical behavior |
| `src/realtime/controller.py` (`InterviewController`) | Question order, follow-ups ≤2, 480s wrap-up |
| `src/realtime/evaluate.py` answer labels | Drives adaptive follow-ups |
| `src/plan_loader.py` briefing / sanitization helpers | Safe spoken questions |
| Prep graph nodes + HITL interrupt pattern | Proven LangGraph flow |
| `src/prep/banned.py` + scorecard evidence gate | Guardrails |
| `src/realtime/scorecard.py` + `pdf_report.py` | Evidence-backed hiring artifacts |
| LiveKit token minting **logic** (grants + agent dispatch) | Correct room join pattern |
| Frontend LiveKit subscribe + agent-audio analyser path | Proven 2D lip-sync input |

### Allowed adapter changes (thin)

- Load plan by **interview / application id** instead of a single global file
- Pass `interview_id`, invite metadata, org settings into session bootstrap
- Persist turns to Postgres **in addition to** or behind `InterviewStore` interface
- Swap face rendering behind `AvatarProvider` without touching controller logic
- Replace `token_server` static hosting with a product API that still mints the same LiveKit JWT shape

---

## 4. SaaS gap analysis

| Area | Current | Gap |
|------|---------|-----|
| **Authentication** | None | Email/password or magic link / OAuth; session or JWT; candidate invite auth separate from recruiter auth |
| **Organizations** | None | Workspace, members, roles (owner/admin/recruiter/viewer) |
| **Jobs** | Hardcoded JD file + plan.job fields | CRUD jobs, JD upload/paste, interview params (duration, competencies) |
| **Candidates / applications** | Name string + prep JSON | Candidate records, application per job, resume/GitHub attachment |
| **Invitations** | Open `/token` with any name | Signed invite tokens, expiry, one-time or limited use, status tracking |
| **Interview lifecycle** | Manual CLI + two terminals | States: draft → prep → pending_review → approved → invited → in_progress → completed/partial → evaluated |
| **Question plans** | One global approved file | Per-application plan; recruiter UI for HITL |
| **Persistence** | SQLite + JSON files | Postgres/Supabase for business data; object storage for PDFs/resumes; optional Redis later |
| **Recruiter dashboard** | None (MCP/Claude only) | Jobs, candidates, interviews, evidence, reports |
| **Candidate portal** | Static demo room | Invite-scoped landing, setup, room, completion |
| **Avatar** | Local 2D RMS mouth | Abstraction + later Simli; keep 2D fallback |
| **Deployment** | Localhost | Agent worker + API + web + DB; secrets via env; HTTPS |
| **Observability** | Print logging | Structured logs, request ids, interview_id correlation, error tracking |
| **Security** | CORS `*`, no auth on token | AuthZ on every API; invite validation; rate limits; no secret in git; PII retention policy |
| **Billing** | None | Design org → subscription later; **do not build in early phases** |
| **Concurrency** | Effectively single-plan machine | Many simultaneous interviews need per-session plan binding |

---

## 5. Proposed target architecture

### 5.1 Principle: shell around the engine

```text
┌─────────────────────────────────────────────────────────────┐
│  Web app (Next.js or similar)                               │
│  Recruiter dashboard · Candidate invite flows · Marketing   │
└───────────────┬─────────────────────────────┬───────────────┘
                │ HTTPS API                    │ LiveKit client
                ▼                              ▼
┌──────────────────────────────┐    ┌─────────────────────────┐
│  SaaS API (FastAPI)          │    │  LiveKit Cloud room     │
│  auth · orgs · jobs · invites│    │  candidate ↔ agent A/V  │
│  prep jobs · HITL · reports  │    └───────────┬─────────────┘
│  mint LiveKit tokens         │                │
└───────────┬──────────────────┘                ▼
            │                      ┌─────────────────────────┐
            │                      │  Interview Worker        │
            │                      │  (existing agent.py)     │
            │                      │  + AvatarProvider        │
            │                      │  + InterviewController   │
            │                      └───────────┬─────────────┘
            ▼                                  │
┌──────────────────────────────┐               │
│  PostgreSQL / Supabase       │◄──────────────┘
│  business entities + turns   │   (session events / final flush)
│                              │
│  Object storage (S3/Supabase)│  resumes, PDFs, optional recordings
│  LangGraph Sqlite/Postgres   │  prep checkpoints (worker-local ok)
└──────────────────────────────┘
```

### 5.2 Process topology

1. **Web** — recruiter + candidate UI  
2. **API** — product CRUD, invite validation, token minting, enqueue prep, serve reports  
3. **Prep worker** — existing LangGraph graph, triggered by API (queue or background task)  
4. **Live agent worker** — existing `agent.py` (scale with LiveKit Agents)  
5. **Post-interview worker** — existing evaluator → scorecard → PDF → DB  

MCP remains optional for power users; dashboard is the primary recruiter UX.

### 5.3 Service boundaries (adapters)

Introduce thin interfaces **without** rewriting engines:

| Boundary | Responsibility |
|----------|----------------|
| `PlanRepository` | Load/save approved plans by `application_id` / `interview_id` (replace global file) |
| `InterviewSessionStore` | Protocol implemented today by `InterviewStore`; later dual-write or Postgres |
| `LiveKitTokenService` | Extract mint logic from `token_server` (same grants/dispatch) |
| `PrepService` | Run/resume LangGraph with org-scoped inputs |
| `EvaluationService` | Call existing evaluate/scorecard/pdf modules; persist results |
| `AvatarProvider` | `Local2D` (default) \| `Simli` (later) \| `None` |

### 5.4 Avatar insertion point (design only — do not implement Simli yet)

**Current audio path**

1. Gemini Live produces agent audio inside LiveKit Agents session  
2. Agent participant publishes audio track to the room  
3. Browser subscribes; `remote-audio` element plays  
4. WebAudio analyser drives `#mouth` on local portrait  

**Safest Simli insertion (per LiveKit avatar pattern + prior RESEARCH.md)**

- Vendor avatar joins as a **second participant**; agent audio is fed to the avatar worker; worker publishes synced A/V  
- Frontend prefers avatar video track when present; otherwise falls back to 2D  
- **Do not** couple Simli into `InterviewController`  
- Config: `AVATAR_PROVIDER=local2d|simli|off` (dev default `local2d`)  
- Keep barge-in: mouth/video must follow **actual** audio stop, not LLM tokens  

```text
AgentSession (Gemini)
    │ audio
    ├─► LiveKit room (always)
    └─► AvatarProvider.start(session, room)   # no-op / 2D hint / Simli
Frontend:
    if remote avatar video → show video
    else → Local2DFace(agent audio RMS)
```

### 5.5 Framework choices (practical, minimal)

| Layer | Recommendation | Why |
|-------|----------------|-----|
| API | **FastAPI** (new) | Fits existing Python; replace ThreadingHTTPServer gradually |
| Web | **Next.js (App Router)** or equivalent React SPA | Recruiter SaaS UX; candidate routes; keep LiveKit JS |
| DB | **PostgreSQL via Supabase** | Auth + DB + storage can align; local Postgres for offline |
| Auth | Supabase Auth or Auth.js / Clerk | Prefer one vendor stack to reduce glue |
| Queue (later) | Supabase + background tasks, then Redis/RQ/Celery if needed | Prep/eval can start as API background tasks |
| Agent | Keep **livekit-agents** process | Do not fold into FastAPI request lifecycle |

**Avoid:** rewriting prep in another language; replacing Gemini Live; premature microservices; building a custom WebRTC stack.

---

## 6. Existing objects → SaaS entities

| SaaS entity | Current equivalent | Action |
|-------------|-------------------|--------|
| User | — | **New** |
| Organization | Implied “Northwind” strings | **New** |
| OrganizationMember | — | **New** |
| Job | `inputs/jd.txt` + `plan.job` | **New** + migrate JD text fields |
| Candidate | `plan.candidate` name / resume JSON | **New** |
| Application | Implicit single demo | **New** (job ↔ candidate) |
| InterviewInvite | Open join form | **New** (tokenized URL) |
| QuestionPlan | `output/question_plan.json` + prep JSON | **Migrate** to DB row + JSONB |
| Question | Items inside plan `questions[]` | **Migrate** (table or JSONB array) |
| Interview | `interviews` row in live SQLite | **Migrate** / enrich |
| InterviewTurn | `turns` table | **Migrate** |
| TranscriptSegment | Export `transcript.json` turns | Derive from turns or dual-write |
| Evaluation | `interview_evaluation.json` | **Migrate** |
| CompetencyScore | `scorecard.competencies[]` | **Migrate** |
| Evidence | `evidence_quote` fields | **Migrate** (normalize later) |
| Report | `report.pdf` path | **Migrate** + object storage URL |

**Reuse without rewrite:** controller transcript shape, scorecard schema, plan question schema, banned-topic sanitizer, MCP tool semantics (map to API later).

---

## 7. Proposed database schema (no migrations yet)

PostgreSQL / Supabase oriented. UUIDs as PKs unless noted. Timestamps `timestamptz`. Soft-delete optional later.

### 7.1 Identity & tenancy

**users**  
`id`, `email` (unique), `name`, `avatar_url`, `created_at`, `updated_at`

**organizations**  
`id`, `name`, `slug` (unique), `created_at`, `updated_at`  
*(later: `stripe_customer_id`, plan tier — nullable placeholders only if needed)*

**organization_members**  
`id`, `organization_id` → orgs, `user_id` → users, `role` (`owner|admin|recruiter|viewer`), `created_at`  
**Unique** `(organization_id, user_id)`  
**Index** `(user_id)`

### 7.2 Hiring objects

**jobs**  
`id`, `organization_id`, `title`, `company_name`, `location`, `jd_text`, `jd_structured` (JSONB), `status` (`draft|active|archived`), `interview_duration_seconds` (default 480), `settings` (JSONB: competencies, avatar_mode, …), `created_by`, `created_at`, `updated_at`  
**Index** `(organization_id, status)`

**candidates**  
`id`, `organization_id` (nullable if global person), `email`, `full_name`, `github_url`, `created_at`  
**Unique** optional `(organization_id, email)`

**applications**  
`id`, `organization_id`, `job_id`, `candidate_id`, `status` (`applied|preparing|pending_review|approved|invited|interviewing|completed|rejected|withdrawn`), `resume_storage_key`, `github_url`, `prep_thread_id`, `created_at`, `updated_at`  
**Index** `(job_id, status)`, `(organization_id, created_at desc)`

### 7.3 Plans & invites

**question_plans**  
`id`, `application_id` (unique active), `organization_id`, `version`, `status` (`pending|approved|rejected`), `approved_by_human` bool, `approval_status`, `edits_made` (JSONB), `plan_json` (JSONB — full current plan for engine compatibility), `created_at`, `updated_at`

**questions** *(optional normalize; JSONB-only OK in Phase 1–3)*  
`id`, `question_plan_id`, `external_key` (`q1`…), `text`, `competency`, `source`, `source_reference`, `difficulty`, `follow_up_triggers` (JSONB), `sort_order`

**interview_invites**  
`id`, `application_id`, `organization_id`, `token_hash` (unique), `expires_at`, `max_uses`, `use_count`, `revoked_at`, `created_by`, `created_at`  
**Index** `(token_hash)`, `(application_id)`

### 7.4 Live interview & evaluation

**interviews**  
`id`, `organization_id`, `application_id`, `job_id`, `question_plan_id`, `invite_id`, `livekit_room`, `livekit_identity`, `status` (`created|running|completed|partial|disconnected|failed`), `phase`, `started_at`, `ended_at`, `elapsed_seconds`, `current_question_id`, `current_question_index`, `follow_up_count`, `completed_question_ids` (JSONB), `created_at`, `updated_at`  
**Index** `(organization_id, created_at desc)`, `(application_id)`, `(status)`

**interview_turns**  
`id`, `interview_id`, `speaker`, `question_id`, `turn_type`, `text`, `timestamp`, `event_id`, `interrupted` bool default false  
**Unique** `(interview_id, event_id)` where event_id present  
**Index** `(interview_id, timestamp)`

**evaluations**  
`id`, `interview_id` (unique), `overall_score`, `recommendation`, `recommendation_reasoning`, `strengths` (JSONB), `concerns` (JSONB), `guardrail_flags` (JSONB), `raw_json` (JSONB), `created_at`

**competency_scores**  
`id`, `evaluation_id`, `name`, `score`, `confidence`, `evidence_quote`, `reasoning`

**reports**  
`id`, `interview_id` (unique), `storage_key`, `content_type`, `generated_at`

### 7.5 Files

**assets** (optional unified)  
`id`, `organization_id`, `kind` (`resume|jd|report|recording`), `storage_key`, `filename`, `created_at`

### 7.6 What stays SQLite (for now)

- LangGraph prep checkpointer (local/worker file or later Postgres checkpointer)
- Optional **dev-only** mirror of live turns for offline scripts  
Production source of truth for product UI: **Postgres**.

---

## 8. Frontend route structure

### 8.1 Public

| Route | Purpose |
|-------|---------|
| `/` | Marketing / product home |
| `/pricing` | Plans (static copy OK until billing) |
| `/login` | Recruiter login |
| `/signup` | Recruiter signup |
| `/legal/privacy`, `/legal/terms` | Consent & compliance |

### 8.2 Recruiter (authenticated, org-scoped)

| Route | Purpose |
|-------|---------|
| `/dashboard` | Pipeline summary, recent interviews |
| `/jobs` | Job list |
| `/jobs/new` | Create job + JD |
| `/jobs/[jobId]` | Job overview + settings |
| `/jobs/[jobId]/candidates` | Applications for job |
| `/jobs/[jobId]/candidates/invite` | Invite flow |
| `/candidates/[candidateId]` | Candidate profile across jobs |
| `/applications/[applicationId]` | Prep status, plan review (HITL) |
| `/applications/[applicationId]/plan` | Question plan approve/edit/reject |
| `/interviews/[interviewId]` | Live status + transcript |
| `/interviews/[interviewId]/report` | Scorecard + evidence |
| `/reports/[reportId]` | PDF download / viewer |
| `/settings` | Org profile |
| `/settings/members` | Members & roles (Phase later) |
| `/settings/billing` | Placeholder only |

### 8.3 Candidate (invite-token scoped — no recruiter account required)

| Route | Purpose |
|-------|---------|
| `/interview/[token]` | Role/company intro |
| `/interview/[token]/setup` | Identity, resume/GitHub confirm, mic check |
| `/interview/[token]/room` | Focused interview room (avatar-first) |
| `/interview/[token]/complete` | Professional completion (no scores) |

### 8.4 Interview room UX (target)

- Avatar / interviewer as primary visual  
- Subtle role title  
- State: connecting / listening / speaking  
- Elapsed time + `Question N of 12`  
- Mic + connection indicators  
- End call where appropriate  
- Optional small candidate self-view  
- **No** debug logs, stack traces, or developer chrome  

### 8.5 Design direction

Polished B2B (Linear / Vercel / Stripe Dashboard inspired): strong hierarchy, restrained color, excellent empty/loading/error states, subtle motion. Avoid hackathon glow, glass overload, and badge spam.

### 8.6 Transition from current `frontend/`

1. Keep current static room as **reference implementation** of LiveKit join + 2D face  
2. Port room behavior into `/interview/[token]/room`  
3. Retire open `/` demo join once invites work  
4. Do not delete working room JS until the new room is parity-tested  

---

## 9. Migration plan (staged)

Adjusted sequence: foundation and **plan-binding** before heavy UI, so the engine can serve many candidates safely.

### Phase 1 — Architecture & SaaS foundation ✅

- FastAPI app at `src/api/main.py` with org/job/candidate/application/interview routes
- SQLAlchemy models + Alembic initial migration (Postgres-compatible; SQLite for local/dev)
- `PlanRepository` (`FilePlanRepository` + `DatabasePlanRepository`)
- Shared `LiveKitTokenService` (token_server delegates here)
- `InterviewSessionStore` adapter over existing `InterviewStore` (no dual-write yet)
- Auth placeholders in `auth/placeholders.py`
- Dev seed: `python src/api/seed.py`
- Backend tests under `tests/`; legacy `run_phase8_checks` / `run_phase9_checks` remain green

**Exit criteria:** met — API healthcheck; DB migrations; engine still runs via CLI / token_server.

### Phase 2 — Premium frontend shell & recruiter dashboard (read-mostly)

- Next.js app with auth pages + dashboard layout  
- Design system tokens (typography, spacing, cards, skeletons)  
- Wire dashboard to **mock or thin APIs** first if needed  
- Do not block on Simli  

**Exit criteria:** Recruiter can log in and see empty states that look production-ready.

### Phase 3 — Jobs, candidates, invites

- CRUD jobs + JD  
- Candidates / applications  
- Invite token generation + email (or copy-link MVP)  
- Store resumes in object storage  

**Exit criteria:** Recruiter creates job and invite link without terminal.

### Phase 4 — Candidate interview experience

- Token-gated landing → setup → room → complete  
- System check (mic, permissions, browser)  
- Port LiveKit join from current `frontend/app.js`  
- Progress/timer parity with `interview_ui`  

**Exit criteria:** Candidate completes a room join on invite URL (even if plan still seeded).

### Phase 5 — Connect interview engine to SaaS entities (**critical**)

- Prep triggered per `application_id` (wrap `prepare_interview` / graph)  
- HITL in recruiter UI (approve/edit/reject) writing `question_plans`  
- Agent loads plan via `PlanRepository.get_for_interview(interview_id)` — **remove global single-plan assumption**  
- Token mint requires valid invite → creates `interviews` row → room name tied to id  
- Persist turns through `InterviewSessionStore` → Postgres  
- On complete/partial: run existing evaluation → scorecard → PDF → `evaluations` / `reports`  

**Exit criteria:** End-to-end SaaS path uses protected engine without CLI for the happy path.

### Phase 6 — Simli avatar integration

- Implement `AvatarProvider` (`Local2D` default, `Simli` optional)  
- Frontend: prefer avatar video track when present  
- Feature flag per org/job; minute budget guards  
- Never require Simli for local/dev  

**Exit criteria:** Flag-on Simli smoke test; flag-off identical to today’s 2D behavior.

### Phase 7 — Analytics, reports, polish

- Recruiter transcript + evidence explorer  
- Competency charts, strengths/concerns, download PDF  
- Empty/loading/error polish; email “interview complete”  
- Optional: map MCP tools to authenticated HTTP for Claude (secondary)  

### Phase 8 — Production hardening

- HTTPS, secrets management, CORS lockdown  
- Rate limits on invite + token endpoints  
- Structured logging + error tracking (Sentry or similar)  
- Backups, PII retention, consent copy  
- Horizontal considerations for agent workers  
- Billing schema hooks only when ready (Tier 8b)  

---

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Global `question_plan.json` | Wrong questions / data leak across candidates | Phase 5 plan-by-id before multi-tenant launch |
| Rewriting realtime stack | Breaks barge-in / latency | Protected list; adapter-only changes |
| Simli minutes / latency | Cost + UX regressions | Default Local2D; gate Simli; tie lips to real audio |
| Auth on LiveKit token endpoint | Unauthorized interviews | Invite validation + short-lived tokens |
| Dual SQLite + Postgres drift | Inconsistent UI | Single writer interface; dual-write briefly then cut over |
| Large Next.js rewrite of room | Regressions | Port proven `app.js` behaviors with checklist |
| PII in logs/transcripts | Compliance | Redact secrets; access control; retention policy |
| Agent process coupled to laptop | No SaaS reliability | Deploy worker separately early in Phase 5–8 |
| Scope creep (billing, live coding, vision) | Delays core promise | Explicitly defer; architecture leaves room |

---

## 11. Recommended implementation order (near-term)

1. **Keep engine green** — existing `agent.py` + `token_server` + prep CLI remain the source of truth until Phase 5 cutover.  
2. **Add API + DB skeleton** without moving files aggressively.  
3. **Build recruiter shell UI** (auth + empty dashboard).  
4. **Jobs → applications → invites**.  
5. **Candidate invite room** (parity with current room).  
6. **Bind plans & interviews to DB ids**; only then deprecate global plan file for production.  
7. **Wire post-interview artifacts into dashboard**.  
8. **AvatarProvider + Simli** behind flags.  
9. **Harden & observe**.  

---

## 12. Explicit non-goals for this phase

- Large refactors or mass renames  
- Replacing LiveKit / Gemini Live  
- Implementing Simli now  
- Building billing  
- Deleting MCP, phase check scripts, or working modules  
- Introducing unnecessary new AI frameworks  

---

## 13. Success definition (SaaS MVP)

A recruiter can:

1. Sign up and create an organization  
2. Create a job with a JD  
3. Invite a candidate  
4. Review/approve an AI-generated question plan in the UI  
5. Have the candidate complete a voice interview via invite link  
6. View transcript, competency scores with evidence quotes, and download a PDF  

…while the **same** `InterviewController` + Gemini Live path powers the call.

---

## 14. Appendix — current key paths

| Concern | Path |
|---------|------|
| Config | `src/config.py` |
| Prep graph | `src/graph.py`, `src/nodes/`, `src/prepare_interview.py` |
| Live agent | `src/agent.py` |
| Controller | `src/realtime/controller.py` |
| Live SQLite | `src/realtime/store.py` → `output/live/interview.sqlite` |
| Token HTTP | `src/token_server.py` |
| Frontend room | `frontend/` |
| Scorecard / PDF | `src/realtime/scorecard.py`, `pdf_report.py` |
| MCP | `src/mcp_server.py` |
| Spec | `FirstRound-Final-Test.pdf` |
| Architecture (as-built) | `ARCHITECTURE.md` |
