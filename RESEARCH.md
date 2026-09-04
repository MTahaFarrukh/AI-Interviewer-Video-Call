# FirstRound — Technical Research & Stack Decision

**Status:** research only. Do not implement from this document yet.  
**Spec:** `FirstRound-Final-Test.pdf` (authoritative).  
**Decision rule:** reliability > free availability > low latency > visual quality > architectural complexity.  
**Research date:** 13 August 2026.

---

## 0. Spec summary (what must actually work)

The grader watches a recording and asks one question: *would a real candidate believe they were being interviewed?*

| Phase | Required behavior |
| --- | --- |
| Prep | Recruiter uploads JD + resume PDF. Agent parses both, finds GitHub, reviews real repos, generates a 12-question plan. Recruiter **approve / edit / reject**. Nothing runs without approval. |
| Live | Candidate joins a browser link. AI has a **visible face + natural voice**, greets by name, discloses it is AI, interviews **8+ continuous minutes**, cites real projects, probes shallow answers (max 2), raises difficulty on strong answers, **stops instantly on barge-in**. Dropped call resumes at last node. |
| After | Per-competency score + transcript quote + confidence, hire / no_hire / borderline, transcript, recording, PDF report. MCP server queryable from Claude Desktop. |

All 12 core requirements are mandatory. Voice-only fails #1. A simple 2D portrait + viseme lip-sync **earns full marks**. Photorealistic avatars are explicitly not worth the 24-hour budget.

Latency target from the PDF: **< 1.2 s** from candidate stop-speaking to agent start-speaking. Measure it; do not guess.

---

## 0.1 Constraint conflicts (must be handled before coding)

| Topic | PDF | Team constraint | Decision |
| --- | --- | --- | --- |
| Repo visibility | Public. Private / broken link = **not graded**. | Remain **private**. | Keep private only if the instructor confirmed a private-repo exception in writing. Otherwise this is a **grading-zero risk**. |
| `.env` | Never commit `.env`. Real key in repo = **−5 + rotate**. `.env.example` is key names only. | Instructor asked to upload `.env` to the **private** repo. | Follow the instructor for this private repo. **Never** paste keys in README, videos, MCP screenshots, or chat. If the repo is later made public, strip `.env` first and rotate every key. |
| Videos | 1 min code + 1.5 min demo + **unedited 8+ min raw recording**. No raw recording → demo not graded. | GitHub URL + 1 min + 1.5 min. | Still record the **8+ min raw take**. The PDF grades it. |
| Commits | ≥10 commits **spread across 24h**. One squash is penalised. | — | Commit as we finish each working slice, not in one burst. |

---

## A. Real-time interview transport

### Comparison

| Question | LiveKit Cloud + Agents | Daily.co + Pipecat | Plain WebRTC |
| --- | --- | --- | --- |
| Candidate joins in a browser? | Yes. Agent Console, React starter, or `livekit-client`. | Yes. Daily JS / React. | Yes, but we must build signaling, ICE, TURN. |
| Python agent joins as a participant? | Yes. `livekit-agents` job joins the room. | Yes. `daily-python` / Pipecat `DailyTransport`. | Possible with `aiortc`, high DIY cost. |
| Stream candidate mic to agent? | Yes. WebRTC audio track → `AgentSession`. | Yes. | Yes, if we wire it. |
| Agent returns audio + video? | Yes. Agent publishes audio; avatar worker publishes A/V. | Yes, with more custom wiring. | Yes, if we publish tracks ourselves. |
| Interruption / barge-in | First-class. Gemini Live native interrupt, or VAD + adaptive interruption on pipelines. | Possible via VAD in Pipecat. More assembly. | We would implement VAD, cancel TTS, flush buffers. Highest risk. |
| Usable free tier | **Build plan, no card:** 5,000 WebRTC participant minutes, 1,000 agent-session minutes (if deployed), 100 concurrent participants, 5 concurrent agent sessions, $2.50 Inference credits. Hard cap, no overage. | 10,000 participant minutes/month. Generous transport, weaker official Python agent story for this assignment. | Free if self-hosted. TURN/NAT will eat the 24 hours. |
| Setup complexity | Low. `lk agent init` + Agent Console in a browser. | Medium. Rooms + Pipecat pipeline. | High. |
| Python support | Official Agents SDK, Google / Groq / avatar plugins. | `daily-python` + Pipecat. | `aiortc` only. |
| 24-hour suitability | **Best.** Matches the PDF recommended column. | Viable fallback. | Only if both clouds fail. |

Docs:

- LiveKit pricing: https://livekit.com/pricing
- LiveKit quotas: https://docs.livekit.io/deploy/admin/quotas-and-limits/
- Voice AI quickstart: https://docs.livekit.io/agents/start/voice-ai/
- Turn handling: https://docs.livekit.io/agents/logic/turns/
- Adaptive interruption: https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/
- Daily Video SDK pricing: https://www.daily.co/pricing/video-sdk/

### Decision: LiveKit Cloud

The Python agent is a first-class room participant. The candidate joins through a browser. Microphone audio reaches the agent; the agent can publish audio and (via an avatar worker or a 2D renderer) video. Barge-in is a product feature, not a weekend science project.

**Do not deploy the agent to LiveKit Cloud during the 24 hours** unless we need a public URL bonus. Run locally with `lk agent dev` / `console` so we do not burn the 1,000 hosted agent-session minutes, and so we avoid Build-plan cold starts (10–20 s). Transport minutes (5,000) are plenty for development + the 8-minute take.

Fallback: Daily.co. Last resort: a single-room `aiortc` loopback. Neither is the first build.

---

## B. Real-time voice / brain

The requirement is a **natural conversation with interruption**, not three disconnected APIs.

### B1. Gemini Live API (recommended brain)

| Item | Finding |
| --- | --- |
| STT | Built in. Native audio in. |
| LLM | Built in. Same realtime session. |
| TTS | Built in. Native audio out. Voices such as `Puck`. |
| Streaming | Stateful WebSocket. Audio in 16 kHz PCM; audio out 24 kHz PCM. |
| Interruption | Server sends `interrupted: true`. Client **must discard buffered audio immediately**. LiveKit plugin does this. |
| Latency | Designed for speech-to-speech. Best chance of hitting < 1.2 s. |
| Free limits | Gemini 2.5 Flash Native Audio Live API is **free of charge on the Free tier** (data may be used to improve Google products). Preview models have tighter rate limits. Free-tier concurrent Live WebSockets are limited (treat as a handful of sessions, not a farm). |
| Keys | `GOOGLE_API_KEY` from Google AI Studio. |
| LiveKit | Official: `livekit-agents[google]`, `google.realtime.RealtimeModel`. |
| Complexity | Lowest path to a talking agent. Hour 0–3 of the PDF plan. |

**Model choice (critical):** use **`gemini-2.5-flash-native-audio-preview-12-2025`**, not `gemini-3.1-flash-live-preview`.

Gemini 3.1 Live **rejects mid-session `send_client_content`**. LiveKit’s `generate_reply()`, `update_instructions()`, and `update_chat_ctx()` are ignored after the first model turn. We need mid-session instruction updates to move intro → resume_probe → jd_fit → github_deepdive. 2.5 supports that.

Enable **context window compression** and **session resumption**. Official guidance: without compression, native-audio tokens (~25/s) can exhaust the window (~15 min audio-only). An 8-minute interview is close to that edge. Resumption tokens survive server-side WebSocket resets (valid 2 hours).

Do **not** turn on candidate video to Gemini during the core interview unless we attempt the “agent sees the candidate” bonus. Video tokens burn the context window much faster (official note: ~2 minutes without compression).

Docs:

- Gemini Live API: https://ai.google.dev/gemini-api/docs/live
- Live API overview: https://ai.google.dev/gemini-api/docs/live-api
- Best practices (interrupt + compression + resumption): https://ai.google.dev/gemini-api/docs/live-api/best-practices
- Pricing (Native Audio Free tier): https://ai.google.dev/gemini-api/docs/pricing
- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Model card: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-native-audio-preview-12-2025
- LiveKit Gemini plugin: https://docs.livekit.io/agents/models/realtime/plugins/gemini/
- Google + LiveKit: https://docs.livekit.io/agents/integrations/google/

### B2. Groq STT + LLM + TTS pipeline (official fallback)

| Item | Finding |
| --- | --- |
| STT | `whisper-large-v3-turbo`. Free: 20 RPM, 2,000 RPD, 7,200 audio-seconds/hour. |
| LLM | `llama-3.1-8b-instant` (14,400 RPD, safest quota) or `llama-3.3-70b-versatile` / `openai/gpt-oss-20b` (1,000 RPD). |
| TTS | PlayAI TTS was **deprecated late 2025**. Groq now exposes Orpheus (`canopylabs/orpheus-v1-english`) at **10 RPM / 100 RPD** — too thin for a full interview day. Do not rely on Groq TTS. |
| Streaming | LiveKit Agents streams STT → LLM → TTS and cancels TTS on VAD barge-in. |
| Interruption | Reliable **if** we use LiveKit VAD / adaptive interruption. Not native speech-to-speech. False interrupts from keyboard noise are the main quality risk. |
| Latency | Typical cascade 0.6–1.4 s. May miss the 1.2 s target on a slow turn. |
| Free limits | No card. Org-level rate limits. Multiple API keys do **not** multiply quota. |
| Keys | `GROQ_API_KEY`. Plus a **separate TTS** key if Groq TTS is unusable (Cartesia or LiveKit Inference). |
| LiveKit | Official Groq plugin for STT / LLM / TTS. |
| Complexity | Higher than Gemini Live. More moving parts, more keys, more barge-in tuning. |

Docs:

- Groq rate limits: https://console.groq.com/docs/rate-limits
- LiveKit Groq: https://docs.livekit.io/agents/integrations/groq/
- LiveKit pipeline architecture: https://livekit.com/blog/sequential-pipeline-architecture-voice-agents
- Cartesia pricing (TTS fallback): https://www.cartesia.ai/pricing
- Cartesia + LiveKit: https://docs.livekit.io/agents/models/tts/cartesia/

### B3. Other options (not recommended as primary)

| Option | Why not first |
| --- | --- |
| OpenAI Realtime | Excellent barge-in. **Not free-tier friendly** for this assignment. |
| LiveKit Inference STT-LLM-TTS (Deepgram / Gemma / Inworld) | Easiest pipeline, but only **$2.50** free Inference credit. Fine as a 10-minute smoke test, not as the interview brain. |
| AssemblyAI Voice Agent + Daily | Viable, extra vendor, not the PDF recommended path. |

### Decision: Gemini Live on LiveKit

Gemini Live is the only free option that is a **single conversational brain** with native interruption. Groq is the PDF fallback for STT + LLM; pair it with Cartesia or LiveKit Inference TTS, not Groq Orpheus, if Gemini Live is down.

Offline prep / scoring / evals should use **Gemini Flash text** (same `GOOGLE_API_KEY`), not the Live WebSocket. Keep Live minutes and concurrent sockets for the actual call.

---

## C. AI face / avatar

PDF: *The face is mandatory — the vendor is not. A simple 2D avatar (portrait + viseme lip-sync driven by the TTS stream) earns full marks.*

### Provider scorecard

| Provider | Free / signup | Recurring free | 8+ min interview? | LiveKit plugin | Lip-sync | Dev without burning minutes? | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **2D viseme (in-app)** | Unlimited | Unlimited | Yes | Not needed. Frontend listens to agent audio. | Amplitude / viseme from TTS stream. Good enough. | Yes. Always on. | **Primary.** |
| **Simli** | ~$10 signup credit (vendor site). API key + face ID. | Vendor site: **50 min/month** on free. | No published per-call cap. 8 min is feasible. | Official Python plugin. | Speech-to-video, <300 ms claimed. | Yes, if gated by `ENABLE_AVATAR=simli`. | **Optional polish** for the final take only. |
| **Tavus / LiveAvatar** | Free plan ~20–25 conversational minutes/month. API key. Stock replica / PAL. | Monthly minutes, no rollover. | **Risk:** secondary sources report a **5 min max conversation** on Free. PAL must be `pipeline_mode=echo` + LiveKit transport. Photorealistic. | Official Python + Node. | Strong, higher latency/complexity. | Only if we never start `AvatarSession` in dev. | Reject for core. Minutes + possible 5-min cap + visual risk. |
| **Anam** | 30 min/month, API key, 1 custom avatar. | 30 min/month, no overage on Free. | **No. Official Free cap is 3 minutes per conversation.** Starter is 5 min. Explorer (paid) is 10 min. | Official. | Good. | Yes if gated, but cannot legally finish the 8-min take on Free. | Reject for the raw recording. |
| **D-ID** | 200 free conversation sessions (Agents product). Credit-based. | After trial, plan-dependent. | **No for a real interview.** Agents FAQ: **5 agent messages per session**, then a new session is billed. Credits per 15 s of speech. | Official, v4 expressive avatars only. | Good for clips, not 8-min dialogue. | Yes if gated. | Reject. |
| **bitHuman** | 99 credits/month featured agents; can self-host a model. | Limited cloud credits. | Possible if self-hosted `.imx` model. Extra GPU/setup. | Official Python. | On-device possible. | Yes if local model. | Too much setup for 24 h. |

Docs:

- LiveKit avatar overview (disable pattern is “don’t start `AvatarSession`”): https://docs.livekit.io/agents/models/avatar/
- Simli plugin: https://docs.livekit.io/agents/models/avatar/plugins/simli/
- Simli docs: https://docs.simli.com/
- Simli LiveKit guide: https://docs.simli.com/api-reference/livekit
- Simli site / pricing claims: https://www.simli.com/
- Tavus plugin: https://docs.livekit.io/agents/models/avatar/plugins/tavus/
- Anam pricing (3 min Free cap): https://anam.ai/pricing
- Anam LiveKit quickstart: https://anam.ai/docs/integrations/livekit/quickstart
- D-ID plugin: https://docs.livekit.io/agents/models/avatar/plugins/did/
- D-ID Agents FAQ (5 messages / 200 free sessions): https://www.d-id.com/faqs/
- bitHuman: https://www.bithuman.ai/

### How LiveKit avatars work (why we can turn them off)

The vendor joins as a **second participant**. Agent audio is sent to the avatar worker; the worker publishes synced A/V. Frontend should use `useVoiceAssistant()` so it shows the worker’s video, not a blank agent tile.

```text
ENABLE_AVATAR=off     → agent publishes audio only; frontend 2D face animates from that audio
ENABLE_AVATAR=2d      → same, plus we treat 2D as the official face (default)
ENABLE_AVATAR=simli   → start simli.AvatarSession; hide 2D; use only for final recording
```

Setup if we ever enable Simli: `SIMLI_API_KEY`, `SIMLI_FACE_ID` from https://app.simli.com/apikey and the default face library. One smoke test ≤ 2 minutes, then off.

### Decision: 2D lip-synced avatar as the scored face

Reliability and minutes both point here. Simli is a gated extra, not the development path. Anam / D-ID / Tavus Free cannot be trusted for an 8-minute continuous interview.

2D implementation sketch (for later, not now):

1. One professional portrait in `frontend/public/avatar.png` (not a celebrity; not a photoreal clone of a real person).
2. Browser `AnalyserNode` on the agent audio track.
3. 4–6 mouth shapes (closed / slightly open / mid / wide / teeth) swapped from RMS, or viseme events if the TTS path exposes them.
4. Idle blink. Nameplate: “FirstRound AI interviewer (AI)”.
5. On barge-in, audio stops → mouth returns to closed in < 200 ms.

That satisfies “visible face + voice synced” without a vendor.

---

## D. GitHub grounding

Use the GitHub REST API with a fine-grained or classic PAT (`repo` not required for public candidate repos; `public_repo` is enough). Authenticated: **5,000 req/h**. Unauthenticated: **60/h** — too low once we start reading files. Cache every response to `output/prep/github.json`.

Docs:

- Repos: https://docs.github.com/en/rest/repos/repos
- Contents / README: https://docs.github.com/en/rest/repos/contents
- Commits: https://docs.github.com/en/rest/commits/commits
- Rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Languages: `GET /repos/{owner}/{repo}/languages`

### Recommended pipeline (simple, evidence-first)

1. **Extract GitHub URL** from resume text with a tight regex (`github.com/[A-Za-z0-9-]+`), then confirm with the LLM. If missing, HITL must supply it — do not invent a username.
2. **Resolve user:** `GET /users/{username}` then `GET /users/{username}/repos?per_page=100&sort=updated&type=owner`.
3. **Pick top 3 relevant repos** (deterministic score, then LLM tie-break):
   - drop forks unless the README shows substantial original work
   - language overlap with JD (Python / JS / TS / etc.)
   - keyword overlap: JD must-haves vs repo name + description + topics
   - recency (`pushed_at`) and a small stars bonus
   - never pick empty / license-only repos
4. **Per repo, pull evidence:**
   - `GET /repos/{owner}/{repo}` (description, language, default branch)
   - `GET /repos/{owner}/{repo}/readme` (decode base64)
   - `GET /repos/{owner}/{repo}/languages`
   - `GET /repos/{owner}/{repo}/commits?per_page=10`
   - `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` **or** `GET /contents/` on likely roots (`src/`, `app/`, `backend/`)
5. **Select 2–4 files per repo** whose paths match JD terms (`rag`, `auth`, `schema`, `component`, `api`, …). Fetch with `GET /contents/{path}`. Truncate each file to ~4–8 KB. Skip lockfiles, images, `node_modules`, minified bundles.
6. **Generate ≥3 GitHub-grounded questions** with:
   - `source: "github"`
   - `source_reference: "{owner}/{repo}/{path}@{sha}"` or `{owner}/{repo}/commit/{sha}`
   - question text that is unanswerable without that file/commit (e.g. “In `src/rag/chunker.py` you split on 512 tokens — why not 256?”)
7. **Guard:** if a question cannot point at a real path or SHA stored in `github.json`, drop it. Generic “tell me about your projects” does not count.

Do **not** use the Code Search API unless we must. It has a stricter secondary rate limit and extra headers. Tree + contents is enough.

Private candidate repos: ask the candidate for a PAT or skip that repo. Never scrape authenticated pages in the browser.

---

## E. PDF parsing

Prefer two small libraries + one LLM structured-output call. No OCR cluster, no Unstructured platform, no vector DB for prep.

| Library | Role | Docs |
| --- | --- | --- |
| **pdfplumber** (primary) | Text + tables + layout-aware extraction. Survives two-column resumes better than raw pypdf. | https://github.com/jsvine/pdfplumber |
| **pypdf** (fallback) | Pure-Python text extract when pdfplumber chokes. Use `strict=False`. | https://pypdf.readthedocs.io/en/stable/user/extract-text.html |
| **Gemini Flash + Pydantic** | Map messy text → `jd.json` / `resume.json`. | https://ai.google.dev/gemini-api/docs/structured-output |

### Approach

1. Extract raw text (pdfplumber `extract_text(layout=True)` per page; concatenate).
2. If page text is nearly empty, retry pypdf, then flag `needs_review` (scanned PDF). For this assignment, ask the candidate for a text-based resume rather than adding Tesseract.
3. Regex pass **before** the LLM:
   - GitHub / LinkedIn / email / phone
   - Redact national ID, home address, phone from stored JSON (PDF privacy rule).
4. LLM structured output into the exact prep schemas (competencies, must-haves, seniority, roles, claims, skills, links).
5. Persist `output/prep/jd.json` and `output/prep/resume.json`. No manual field entry.

JD may arrive as `inputs/jd.txt` (PDF allows this). Treat `.txt` as already-extracted text and skip the PDF step.

---

## F. LangGraph — recommended architecture (not implemented)

Docs:

- Interrupts / HITL: https://docs.langchain.com/oss/python/langgraph/interrupts
- Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- Checkpointers: https://docs.langchain.com/oss/python/langgraph/checkpointers
- `SqliteSaver`: https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver
- Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api

Use **one `StateGraph`** so the viva can open `src/graph.py` and see typed state, ≥6 nodes, ≥2 conditional edges, and a real interrupt. Compile with `SqliteSaver` / `AsyncSqliteSaver` (`check_same_thread=False`). `thread_id = interview_id`.

### Typed state (minimum)

```text
interview_id, thread_id
jd: parsed JD
resume: parsed resume
github: repos + files + commits
gaps: claim vs JD vs GitHub
question_plan: 12 questions
approval: pending | approved | edited | rejected
edits_made: list
phase: prep | intro | resume_probe | jd_fit | github_deepdive | scenario | candidate_qs | wrap_up | scoring
current_q_id, follow_up_count (0–2)
last_answer_quality: shallow | adequate | strong | bluff | silence | off_topic
transcript: list[Turn]
scores, recommendation
elapsed_seconds, barge_in_count
guardrail_flags
```

Use `TypedDict` or Pydantic. Reducers: append-only transcript; overwrite plan/scores.

### Nodes (≥6; we should ship ~12 so the diagram matches the PDF)

**Prep**

1. `parse_jd`
2. `parse_resume`
3. `github_agent`
4. `gap_analysis`
5. `question_planner` — 12 Qs, ≥3 GitHub-cited; run banned-question filter here
6. `hitl_gate` — **`interrupt({plan, gaps})`**. Resume payload: `{action: approve|edit|reject, edits?: [...]}`

**Live** (driven by the voice agent; graph is the source of truth)

7. `intro`
8. `ask_question` — next item from the approved plan, phase-aware
9. `evaluate_answer` — shallow / strong / bluff / silence / off-topic
10. `follow_up` — increment `follow_up_count`; cap 2
11. `verify_bluff` — “walk me through that commit / file”
12. `recover` — 15 s silence or off-topic
13. `wrap_up`

**Score**

14. `score_competencies`
15. `evidence_guardrail` — reject any score whose quote is not a substring of the transcript
16. `write_outputs` — `scorecard.json`, `transcript.json`, `report.pdf`

### Conditional edges (≥2; ship these four)

1. **`after_hitl`:** reject → `question_planner`; edit → apply edits then `intro`; approve → `intro`.
2. **`after_evaluate`:**
   - `elapsed_seconds >= 480` or phase is last → `wrap_up`
   - silence / off-topic → `recover`
   - bluff → `verify_bluff`
   - shallow **and** `follow_up_count < 2` → `follow_up`
   - strong → bump next question difficulty, then `ask_question`
   - else → `ask_question` (advance phase when the planned questions for this phase are done)
3. **`after_follow_up`:** if still shallow and cap not reached → `ask_question` (probe); else advance.
4. **`after_recover`:** if still silent after one recovery prompt → `wrap_up`; else continue current phase.

A linear chain with fake `if` comments will have LangGraph marks halved. These routers must be real `add_conditional_edges`.

### HITL

```text
hitl_gate:
  decision = interrupt({"type": "approve_plan", "plan": state.question_plan})
  # node restarts from the top on resume — keep side effects AFTER interrupt
  return apply_decision(decision)
```

Resume with the same `thread_id`:

```text
graph.invoke(Command(resume={"action": "approve"}), config)
graph.invoke(Command(resume={"action": "edit", "edits": [...]}), config)
graph.invoke(Command(resume={"action": "reject", "reason": "..."}), config)
```

Recruiter UI can be a tiny local page or a CLI. Proof = screenshot + this code.

### Call-drop recovery

- Checkpointer writes after every live node.
- LiveKit / Gemini session **dies** on disconnect. That is expected.
- On rejoin, load checkpoint by `interview_id`, skip prep/HITL, speak: “We were disconnected. We were on {phase}, question {n}.”
- Do not replay the whole interview. Do not reset `follow_up_count` or transcript.

### How LangGraph talks to the voice agent

Do not put WebRTC inside LangGraph nodes.

- **Prep + HITL + scoring:** `graph.invoke` from a small FastAPI / CLI.
- **Live:** LiveKit `Agent` holds the Gemini session. After each candidate turn, a tool `advance_interview(transcript_turn)` invokes the graph with the new answer and receives `{speak, next_phase, question, interrupted}`.
- System instructions update per phase (`update_instructions` — works on Gemini 2.5).
- Prompts live in `prompts/*.md` with `prompts/ITERATION_NOTES.md`.

This keeps barge-in in LiveKit (milliseconds) and interview logic in LangGraph (viva-visible).

---

## G. MCP

Simplest path: **FastMCP, stdio, Claude Desktop**.

Docs:

- FastMCP: https://gofastmcp.com/getting-started/welcome
- Claude Desktop install: https://gofastmcp.com/integrations/claude-desktop
- Official user quickstart: https://modelcontextprotocol.io/quickstart/user

Five required tools, all reading/writing the same SQLite + `output/` files:

| Tool | Returns |
| --- | --- |
| `get_candidate(interview_id)` | name, role, resume summary, GitHub user, status. Unknown ID → explicit error object, not a crash. |
| `get_question_plan(interview_id)` | plan + `approved_by_human` + edits. |
| `save_score(interview_id, scorecard)` | validates schema + evidence guardrail, writes `output/scorecard.json`. |
| `get_scorecard(interview_id)` | current scorecard or “not scored yet”. |
| `list_interviews()` | id, candidate, role, date, recommendation. |

Windows Claude config (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "firstround": {
      "command": "uv",
      "args": ["run", "--directory", "D:/Courses/Agentic AI FAST/AI-Season-Final", "python", "mcp_server/server.py"],
      "env": {}
    }
  }
}
```

Claude Desktop **does not inherit the user shell**. Pass env explicitly if a tool needs keys. Restart Claude fully; hammer icon = tools loaded. Screenshot that for deliverable #8.

Do not spend time on HTTP MCP. Stdio is what Claude Desktop actually uses for local servers.

---

## H. Scorecard + guardrails

### Evidence quote

Every competency object must include `evidence_quote` copied **verbatim** from `transcript.json`. `guardrails/evidence_check.py`:

- normalize whitespace
- require quote length ≥ 12 characters
- require quote to appear in some candidate (or agent+candidate) turn
- if missing → score row status `REJECTED`, add `guardrail_flags`, do not emit a 1–5 number for that competency until fixed

The scorer LLM must be instructed: *if you cannot quote, return `score: null`*. A second deterministic pass enforces it. Tests prove both the LLM path and the deterministic reject.

### Banned questions

Block **before the candidate hears them** — in `question_planner` and again in `ask_question`.

Banned (PDF): age, gender, marital status, religion, nationality, health/pregnancy, salary history, politics.

Implementation: keyword / regex list + a small LLM classifier for paraphrases (“how old were you when…”). On hit: replace with a safe backup from the plan, append `guardrail_flags`. Unit test: inject “What is your religion?” and prove it never reaches the speak payload.

### Recommendation

Map overall 1–5 mean (or weighted competencies):

| Mean | Recommendation |
| --- | --- |
| ≥ 4.0 | `hire` |
| 3.0–3.9 | `borderline` |
| < 3.0 | `no_hire` |

Confidence is not the score. High confidence = many specific quotes + GitHub answers that matched `github.json`. Low confidence = short interview, missing GitHub, or scorer disagreement.

### Evals (do not skip)

Synthetic transcripts for the five personas in `evals/personas/`. `run_evals.py` must rank **Strong > Average > Weak**, put Bluffer **below Average**, and Nervous **near Strong**. Honest failure in `evals/results.md` scores better than a perfect table.

---

## I. Development strategy (protect avatar minutes)

Assume Simli (or any vendor) is **scarce**. The 2D face is always available.

### Modes

| Mode | Transport | Brain | Face | Use |
| --- | --- | --- | --- | --- |
| `text` | none | Gemini Flash / Groq LLM | none | LangGraph, HITL, GitHub, scorer, evals, MCP |
| `voice` | LiveKit | Gemini Live | 2D from audio | barge-in, latency, 8-min rehearsal |
| `avatar` | LiveKit | Gemini Live | Simli | one 90 s integration test + optional final take |

`FIRSTROUND_MODE=text|voice|avatar` in `.env`. Default `text`.

### Minute budget if Simli is used at all

| Spend | Minutes |
| --- | --- |
| Integration smoke (once) | 2 |
| Raw 8+ min recording (one good take) | 10 |
| Demo retake buffer | 4 |
| Emergency second raw take | 10 |
| **Reserve** | **~24** |
| **Do not use** | all other hours |

If the 2D face looks acceptable on camera, **never enable Simli**. The PDF awards full marks either way.

### 24-hour sequence (aligned with the PDF, avatar-safe)

| Hours | Goal | Avatar? |
| --- | --- | --- |
| 0–1 | Verify every key: LiveKit room join, Gemini Live 15 s hello, Groq ping, GitHub `/rate_limit`, pdfplumber on `inputs/resume.pdf`. | off |
| 1–3 | Browser join + Gemini Live agent speaks and stops on interrupt. Measure latency. 2D mouth wired to audio. | 2D only |
| 3–5 | Prep graph: JD, resume, GitHub, plan JSON on disk. | off |
| 5–7 | Full LangGraph: routers, follow-up cap, checkpointer, text-mode live loop. | off |
| 7–8 | HITL approve/edit/reject + MCP in Claude Desktop. | off |
| 8–9 | Guardrails + tests + scorecard writer. | off |
| 9 | **Optional 90 s Simli smoke.** Then disable. | 2 min max |
| 9–11 | Sleep. | — |
| 11–13 | Evals + prompt v1→v2 notes. | off |
| 13–15 | Real 8+ min interview, 2D face, OBS/browser capture. Budget two takes. | 2D (Simli only if 2D failed) |
| 15–17 | Bonus only if all 12 work. Prefer one Tier 2. | off |
| 17–19 | ARCHITECTURE, README, SUBMISSION, prompt notes. | off |
| 19–21 | Script and shoot 1:00 + 1:30 videos. Own voice. | 2D or reserved Simli clip |
| 21–24 | Clean-clone test, video links in a private window, submit. | off |

### Recording

Do **not** depend on LiveKit Egress for the graded raw take (extra moving part; 60 transcode minutes). Screen-record the browser with OBS or Windows Game Bar. Keep an unedited 8+ minute file. Consent line in `SUBMISSION.md`.

### What we test without a face vendor

- barge-in (voice mode)
- all LangGraph routers (text mode)
- HITL
- GitHub-grounded questions
- scorecard + both guardrails
- MCP tools
- eval ranking
- call-drop: kill the process, `invoke` same `thread_id`, confirm phase resume

---

## J. Final recommendation

One stack. Fallbacks are listed, not built in parallel.

| # | Layer | Choice | Why |
| --- | --- | --- | --- |
| 1 | Transport | **LiveKit Cloud**, agent run **locally** (`lk agent dev` / console) | Browser join, Python participant, A/V, barge-in, 24-hour setup. |
| 2 | Realtime brain | **Gemini Live** `gemini-2.5-flash-native-audio-preview-12-2025` via LiveKit `RealtimeModel` | Native audio I/O + native interrupt. 3.1 cannot update instructions mid-call. |
| 3 | STT | **Gemini Live built-in** | No extra hop. |
| 4 | TTS | **Gemini Live built-in** | Same session, natural turn-taking. |
| 5 | Avatar | **2D portrait + viseme / amplitude lip-sync** | Full marks, unlimited minutes, no vendor cap. Simli optional and gated. |
| 6 | Backend language | **Python 3.11+** | LiveKit Agents, LangGraph, FastMCP, pdfplumber. |
| 7 | LangGraph | `StateGraph` + typed state + `interrupt()` HITL + 4 routers | Matches §2 and rubric. Voice I/O stays in LiveKit. |
| 8 | Database / checkpointer | **SQLite** file + `SqliteSaver` / `AsyncSqliteSaver` | Required by spec. Same DB for MCP. |
| 9 | PDF parser | **pdfplumber → pypdf fallback → Gemini structured output** | Simple, messy-PDF tolerant. |
| 10 | GitHub | **REST + PAT**, cache to `github.json` | 5,000 req/h. Questions must cite repo/file/commit. |
| 11 | MCP | **FastMCP stdio** → Claude Desktop | Five tools, screenshot proof. |
| 12 | Frontend | **LiveKit Agent Console for dev** + thin **Next.js starter or single HTML page** for the demo (2D canvas + join token) | Do not build a product UI. |
| 13 | Required API keys | See below | Verify in hour 0. |
| 14 | Free-tier limits | See below | Stay inside them. |
| 15 | Biggest risks | See below | Sequence work to kill these first. |
| 16 | Fallbacks | See below | PDF: fallbacks lose no marks. |

### 13. Required API keys

| Key | Required? | Source |
| --- | --- | --- |
| `LIVEKIT_URL` | Yes | https://cloud.livekit.io |
| `LIVEKIT_API_KEY` | Yes | same |
| `LIVEKIT_API_SECRET` | Yes | same |
| `GOOGLE_API_KEY` | Yes | https://aistudio.google.com/apikey |
| `GITHUB_TOKEN` | Yes | https://github.com/settings/tokens (public repo read) |
| `GROQ_API_KEY` | Recommended fallback | https://console.groq.com |
| `CARTESIA_API_KEY` | Only if Gemini Live TTS is down | https://play.cartesia.ai/keys |
| `SIMLI_API_KEY` / `SIMLI_FACE_ID` | Optional | https://app.simli.com/apikey |
| `ENABLE_AVATAR` | Local flag | `off` / `2d` / `simli` |

`.env.example` lists names only. Per instructor, `.env` may live in this **private** repo. Do not show values on camera.

### 14. Estimated free-tier limitations

| Service | Limit that can bite us |
| --- | --- |
| LiveKit Build | 5,000 participant minutes; 5 concurrent agent sessions; 2 egress; hard cap. Hosted agent minutes 1,000 if we deploy. |
| Gemini Live Free | Free tokens, tight RPM / concurrent sockets on preview models. Enable compression for 8+ min. |
| Gemini Flash text | Shared daily RPM/RPD with other Flash usage — enough for prep + evals if we do not loop. |
| Groq Free | 30 RPM class LLMs; Whisper 20 RPM / 2k RPD; Orpheus TTS 100 RPD — unusable as sole TTS. |
| Cartesia Free | ~20k credits/month (~27 TTS minutes claimed on pricing page). |
| GitHub PAT | 5,000 req/h. Cache. |
| Simli Free | Signup credit + ~50 min/month. Treat as ≤ 25 min usable. |
| Anam / Tavus / D-ID Free | Conversation-length or message caps that can **fail the 8-min requirement**. |

### 15. Biggest technical risks

1. **Gemini Live preview instability** (model rename, 1007 on mid-session updates if we pick 3.1, socket reset mid-interview). Mitigation: pin 2.5 native audio, session resumption, compression, Groq pipeline ready.
2. **Barge-in looks fake** if we leave TTS audio buffered, or if a vendor avatar keeps talking after Gemini stops. Mitigation: LiveKit interrupt + 2D mouth tied to **actual** audio energy, not to LLM tokens.
3. **8-minute session dies** from context overflow or a dropped tab. Mitigation: compression, checkpointer, reconnect script, two recording attempts.
4. **GitHub questions are generic.** Mitigation: refuse to emit a GitHub question without a stored path/SHA.
5. **HITL is a `input()` fake.** Mitigation: real `interrupt()` + checkpointer + screenshot.
6. **Private repo / committed `.env`** vs PDF rules. Mitigation: written instructor exception; never leak keys elsewhere.
7. **Avatar minutes gone before the raw take.** Mitigation: 2D is the scored face; Simli off by default.
8. **Latency > 1.2 s** on a Groq cascade. Mitigation: Gemini Live first; measure in ARCHITECTURE.md.
9. **Messy/scanned resume.** Mitigation: pdfplumber + reject scan early; ask for a digital PDF.
10. **Viva:** cannot explain the follow-up edge or the interrupt stop. Mitigation: keep `graph.py` and the barge-in path small and obvious.

### 16. Fallback per major component

| Component | Primary | Fallback (no mark loss per PDF) |
| --- | --- | --- |
| Transport | LiveKit Cloud | Daily.co, then plain WebRTC |
| Brain | Gemini Live 2.5 native audio | Groq Whisper + Groq LLM + Cartesia/LiveKit Inference TTS |
| STT | Gemini Live | Groq `whisper-large-v3-turbo` |
| TTS | Gemini Live | Cartesia Sonic via plugin or LiveKit Inference; last resort browser `speechSynthesis` |
| Avatar | 2D viseme | Simli gated; never Anam Free / D-ID Agents for the 8-min take |
| Graph | LangGraph + SQLite | (no substitute — required) |
| Checkpointer | `SqliteSaver` | `AsyncSqliteSaver`; never `InMemorySaver` for the demo |
| PDF | pdfplumber | pypdf |
| GitHub | REST + PAT | unauthenticated + hard cache (60/h) |
| MCP | FastMCP stdio | official MCP Python SDK stdio |
| Report | reportlab | WeasyPrint or HTML→PDF; Markdown report is −1 |
| Frontend | Agent Console + thin join page | LiveKit Next.js starter https://docs.livekit.io/frontends/start/starter-apps/react/ |
| Deploy | localhost (allowed; bonus only if public) | Render / Railway only after core 12 work |

---

## Official documentation index

| Topic | URL |
| --- | --- |
| LiveKit pricing | https://livekit.com/pricing |
| LiveKit quotas | https://docs.livekit.io/deploy/admin/quotas-and-limits/ |
| LiveKit voice quickstart | https://docs.livekit.io/agents/start/voice-ai/ |
| LiveKit Agent Console | https://docs.livekit.io/agents/start/console/ |
| LiveKit frontends | https://docs.livekit.io/agents/start/frontend/ |
| LiveKit turns / barge-in | https://docs.livekit.io/agents/logic/turns/ |
| LiveKit adaptive interruption | https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/ |
| LiveKit Gemini Live | https://docs.livekit.io/agents/models/realtime/plugins/gemini/ |
| LiveKit Groq | https://docs.livekit.io/agents/integrations/groq/ |
| LiveKit avatars | https://docs.livekit.io/agents/models/avatar/ |
| LiveKit Simli | https://docs.livekit.io/agents/models/avatar/plugins/simli/ |
| Gemini Live | https://ai.google.dev/gemini-api/docs/live |
| Gemini Live best practices | https://ai.google.dev/gemini-api/docs/live-api/best-practices |
| Gemini pricing | https://ai.google.dev/gemini-api/docs/pricing |
| Groq rate limits | https://console.groq.com/docs/rate-limits |
| Daily pricing | https://www.daily.co/pricing/video-sdk/ |
| Anam pricing | https://anam.ai/pricing |
| LangGraph interrupts | https://docs.langchain.com/oss/python/langgraph/interrupts |
| LangGraph persistence | https://docs.langchain.com/oss/python/langgraph/persistence |
| SqliteSaver | https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver |
| FastMCP | https://gofastmcp.com/getting-started/welcome |
| FastMCP + Claude Desktop | https://gofastmcp.com/integrations/claude-desktop |
| GitHub REST repos | https://docs.github.com/en/rest/repos/repos |
| GitHub contents | https://docs.github.com/en/rest/repos/contents |
| GitHub rate limits | https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api |
| pdfplumber | https://github.com/jsvine/pdfplumber |
| pypdf extract | https://pypdf.readthedocs.io/en/stable/user/extract-text.html |
| Cartesia pricing | https://www.cartesia.ai/pricing |

---

## What we will not do in the next step (until asked)

- Scaffold the full `firstround/` tree
- Install a large dependency set
- Sign up for Anam / Tavus / D-ID as the scored face
- Build a photorealistic avatar path
- Use Gemini 3.1 Live as the interview model

**Next implementation slice, when approved:** hour-0 key check + a joinable LiveKit room where Gemini Live speaks, listens, and stops on barge-in, with the 2D face driven by agent audio and `ENABLE_AVATAR=off` for any vendor.
