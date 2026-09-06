# FirstRound — Candidate Experience (Phase 3)

**Status:** Phase 3 implemented  
**Date:** 2026-09-06

## Journey

1. Recruiter opens `/interviews/[id]` → **Invite candidate**
2. Backend creates `InterviewInvite` with hashed token; raw token returned once
3. Recruiter copies `/interview/{token}`
4. Candidate opens landing → consent → setup → room → complete

## Invite lifecycle

| Invite status | Meaning |
|---------------|---------|
| `pending` | Created, not opened |
| `opened` | Public invite fetched |
| `accepted` | Consent accepted / session join allowed |
| `completed` | Candidate finished |
| `expired` | Past `expires_at` |
| `revoked` | Recruiter revoked / regenerated previous |

Interview transitions toward `ready` on invite create and `in_progress` on session start.

## Token security

- Raw token: `secrets.token_urlsafe(32)`
- Stored: SHA-256 hex in `token_hash` only
- Never returned from GET invite after creation (only create/regenerate responses include `raw_token`)
- Expiry default 72h; revoke + regenerate supported
- Public payload excludes org IDs, scorecards, question text, recruiter notes

## Candidate routes

| Route | Purpose |
|-------|---------|
| `/interview/[token]` | Landing + consent |
| `/interview/[token]/setup` | Mic/camera/browser checks |
| `/interview/[token]/room` | Premium room shell + LiveKit join |
| `/interview/[token]/complete` | Completion (no scores) |

## LiveKit session boundary

`POST /api/v1/public/interview-invites/{token}/session`

1. Validates invite + consent
2. Ensures `Interview.livekit_room_name = interview_<uuidhex>`
3. Marks interview `in_progress` / sets `started_at`
4. Mints JWT via shared **`LiveKitTokenService`** (same as `token_server`)
5. Returns `{ room_name, participant_identity, livekit_url, token, ... }`

No duplicate JWT implementation.

## Room states

`preparing → connecting → connected/ready → listening/speaking → reconnecting/connection_lost → completed/failed`

## Avatar abstraction

`InterviewerStage` supports `mode: "local" | "simli"`.

Phase 3 renders local placeholder presence (`idle|listening|speaking|connecting`).  
Phase 6 can replace the visual region with Simli video without restructuring the room.

## Phase 4 engine binding requirements

- Pass SaaS `interview_id` / room metadata into `agent.py`
- Load **DB** question plan for that interview (retire global file for SaaS rooms)
- Persist turns against SaaS interview id
- Trigger evaluator/report into product entities

Do **not** rewrite Gemini/LiveKit barge-in or `InterviewController` for that work.
