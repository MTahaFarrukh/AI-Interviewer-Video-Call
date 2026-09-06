# FirstRound — Frontend Architecture

**Status:** Phase 3 candidate experience added  
**Date:** 2026-09-06

## Stack

- **Next.js 15** (App Router) + **TypeScript**
- **Tailwind CSS v4**
- Lightweight UI primitives (Button, Card, Badge, Input) inspired by shadcn patterns
- **Lucide** icons
- **livekit-client** for candidate room join
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
| `/interviews/[id]` | Review + invite panel + DB question plan |
| `/settings` | Org + dev identity |

### Candidate experience (`/interview`, minimal chrome)

| Route | Purpose |
|-------|---------|
| `/interview/[token]` | Landing + consent |
| `/interview/[token]/setup` | Mic / browser / optional camera checks |
| `/interview/[token]/room` | Premium room shell + LiveKit |
| `/interview/[token]/complete` | Completion (no scores) |

## Component hierarchy

```text
components/
  marketing/     landing chrome + product preview
  candidate/     CandidateChrome, InterviewerStage
  invite-panel.tsx
  ui/            button, badge, card, input, skeleton
  app-sidebar.tsx
  …
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
  invites.ts
lib/interview/
  question-progress.ts   # isolated progress adapter (no global JSON)
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
- recruiter invite calls send `X-Organization-Id` when an org is selected

Replace this module later with Supabase Auth. Do not scatter fake-user logic into pages.

## Avatar abstraction

`InterviewerStage` supports `mode: "local" | "simli"`. Phase 3 renders local placeholder presence only. Simli is intentionally not installed.

## Design system

- Neutral zinc surfaces + indigo primary accent (recruiter shell)
- Candidate room uses dark calm zinc stage (not Meet/Zoom chrome)
- Geist Sans / Geist Mono
- Status badges with restrained tones
- Desktop sidebar + mobile drawer for recruiter app

See also: [`CANDIDATE_EXPERIENCE.md`](CANDIDATE_EXPERIENCE.md)
