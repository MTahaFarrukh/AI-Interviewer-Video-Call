# FirstRound — Frontend Architecture (Phase 2)

**Status:** Phase 2 implemented  
**Date:** 2026-09-06

## Stack

- **Next.js 15** (App Router) + **TypeScript**
- **Tailwind CSS v4**
- Lightweight UI primitives (Button, Card, Badge, Input) inspired by shadcn patterns
- **Lucide** icons
- **Vitest** + Testing Library

Location: `web/`  
Legacy LiveKit candidate room remains in `frontend/` (untouched).

## Route structure

### Public

| Route | Purpose |
|-------|---------|
| `/` | SaaS landing |
| `/pricing` | Early-access pricing tiers |
| `/login` | Demo auth entry |
| `/signup` | Demo workspace entry |

### Recruiter app (`(app)` layout)

| Route | Purpose |
|-------|---------|
| `/dashboard` | Hiring overview |
| `/jobs` | Job list |
| `/jobs/new` | Create job |
| `/jobs/[id]` | Job detail + setup |
| `/candidates` | Candidate list |
| `/candidates/[id]` | Candidate profile |
| `/interviews` | Interview list |
| `/interviews/[id]` | Review foundation + DB question plan |
| `/settings` | Org + dev identity |

Candidate invite/room routes are **not** built in Phase 2.

## Component hierarchy

```text
components/
  marketing/     landing chrome + product preview
  ui/            button, badge, card, input, skeleton
  app-sidebar.tsx
  page-header.tsx
  stat-card.tsx
  status-badge.tsx
  empty-state.tsx
  error-state.tsx
  question-review-card.tsx
```

## API client

```text
lib/api/
  client.ts
  types.ts
  organizations.ts
  jobs.ts
  candidates.ts
  applications.ts
  interviews.ts
```

Configure with:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DEV_ORG_SLUG=northwind-labs
```

Question-plan fetches use `GET /api/v1/interviews/{id}/question-plan` only.  
They never read `output/question_plan.json`.

## Auth / org placeholder strategy

`lib/auth.tsx` holds development identity:

- localStorage demo session
- loads organizations from API
- prefers seeded `northwind-labs`
- organization switcher in sidebar

Replace this module later with Supabase Auth. Do not scatter fake-user logic into pages.

## Design system

- Neutral zinc surfaces + **indigo** primary accent
- Geist Sans / Geist Mono
- Status badges with restrained tones
- Desktop sidebar + mobile drawer
- Light theme primary; CSS variables include `.dark` hooks for later

## Future candidate-room integration

Keep `frontend/` as the LiveKit room reference. Phase 4 should port room behavior into `/interview/[token]/room` while continuing to call the protected engine via LiveKit, not by rewriting `agent.py`.
