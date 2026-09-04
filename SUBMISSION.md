# FirstRound — SUBMISSION

**Project:** FirstRound AI Video Interviewer  
**Course:** AI Season Final Test (`FirstRound-Final-Test.pdf`)  
**Repo:** https://github.com/MTahaFarrukh/AI-Season-Final  
**Branch:** `main`

## Candidate / demo context

- **Graded candidate:** Muhammad Taha Farrukh  
- **Role / JD chosen:** Junior AI Engineer — Northwind Labs, Karachi (JD #1 in the assignment PDF)  
- **Interview id:** `AJ_mPYT3PkhgjPw`  
- **Date:** 2026-08-14  

## Links

| Item | Link |
|------|------|
| GitHub repo | https://github.com/MTahaFarrukh/AI-Season-Final |
| Code video (1 min) | **TO BE FILLED** before portal submit |
| Demo video (1:30) | **TO BE FILLED** before portal submit |
| Raw recording (≥8 min) | **TO BE FILLED** before portal submit (or note examiner waiver if applicable) |
| Claude MCP screenshots | `submission/screenshots/claude-mcp-tools-1.png`, `claude-mcp-tools-2.png` |
| HITL screenshot | `submission/screenshots/hitl-recruiter-review.png` |
| Graded PDF report | `output/report.pdf` |

## What works (core)

- LiveKit + Gemini Live voice interview; local **2D face** + mouth animation  
- Barge-in via LiveKit / Gemini Live interruption (see agent `[INTERRUPT]` logs)  
- JD + resume parsing → `output/prep/*.json`  
- GitHub grounding (≥3 plan questions cite real repo/file/commit)  
- LangGraph prep graph with HITL approve / edit / reject + SQLite checkpointer  
- Adaptive follow-ups capped at **2**; 8-minute (`480s`) timer → wrap-up  
- SQLite live persistence / restore; offline evaluation; evidence-gated scorecard; `report.pdf`  
- FastMCP tools; Claude Desktop **Connectors → firstround** shows tools (screenshots above)  
- Persona evals + prompt iteration notes  

## What is broken / known limitations

- Graded live take is **partial: 9/12 questions**, not a full 12-question completion  
- Strong-answer path advances the plan; it does not dynamically rewrite difficulty mid-topic  
- Live resume uses InterviewStore, not LangGraph on the live call  
- Exported `transcript.json` has `interrupted: false` on all turns (audio barge-in may still occur)  
- Some transcript agent lines look like short labels/triggers, not full spoken text  
- **No bonus features** implemented (no public deploy URL, bias audit, etc.)  
- `.env` with real keys has been tracked in git — remove from tracking, rotate keys before making the repo public  

## Honest graded interview result (current artifacts)

| Field | Value |
|-------|--------|
| Interview id | `AJ_mPYT3PkhgjPw` |
| Duration | 482 seconds |
| Status | partial |
| Questions | 9 of 12 attempted |
| Turns | 38 |
| Overall score (1–5) | **3.6** |
| Recommendation | **borderline** |
| GitHub-grounded questions asked | 3 |
| Artifacts | `output/transcript.json`, `output/scorecard.json`, `output/report.pdf` |
| Prior graded backup | `output/backup-taha-live-20260814/` |

## Barge-in timestamp

**Not filled from a final raw recording timestamp.**  
Fill this after the submission raw recording is finalized (wall-clock or video timecode where the candidate interrupts and the agent stops).  
Log pattern to correlate: `[INTERRUPT] Agent interrupted`.

## Measured latency

- **Spec target:** &lt; 1.2 s (candidate stop → agent audio start)  
- **Measured sample documented in README:** `[LATENCY] candidate_stop_to_agent_audio_ms=842` (**842 ms**)  
- Instrumentation: `src/agent.py` (runtime log; not hardcoded)

## Avatar used

Local **2D portrait** (`frontend/public/avatar.png`) + CSS/JS mouth animation driven by agent audio. Vendor avatar plugins (Simli/Tavus/etc.) **disabled / not implemented**.

## Bonus attempted

**None.** Core-only submission for bonus marks.

## HITL status

Approved plan on disk: `output/question_plan.json` with `approved_by_human: true`, `approval_status: approved`, `sample_mode: false`.

## MCP / Claude Desktop status

- Server: `src/mcp_server.py` (FastMCP stdio)  
- PDF-required tools present: `get_candidate`, `get_question_plan`, `save_score`, `get_scorecard`, `list_interviews` (plus additional read tools)  
- Claude Desktop: **firstround** connector tools visible — proof screenshots:  
  - `submission/screenshots/claude-mcp-tools-1.png`  
  - `submission/screenshots/claude-mcp-tools-2.png`  
- HITL gate proof: `submission/screenshots/hitl-recruiter-review.png`  

## How to run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# copy .env.example → .env and fill keys locally (do not commit secrets)

# Terminal 1 — agent
python src\agent.py start

# Terminal 2 — UI + tokens
python src\token_server.py
# open http://127.0.0.1:8080
```

Prep / HITL: `python src\prepare_interview.py --resume inputs\resume.pdf --jd inputs\jd.txt --github <url>` then approve/edit/reject.

MCP (stdio): `python src\mcp_server.py` (spawned by Claude Desktop).

## Verification / tests (offline)

```powershell
python src\run_phase8_checks.py
python src\run_phase9_checks.py
python evals\run_evals.py
```

## Required artifact paths

```text
output/prep/jd.json
output/prep/resume.json
output/prep/github.json
output/prep/question_plan.json
output/transcript.json
output/scorecard.json
output/report.pdf          ← recruiter PDF scorecard (graded from AJ_mPYT3PkhgjPw)
```

Regenerate graded trio after a live take:

```powershell
python src\generate_grading_artifacts.py
```

(Uses interview id `AJ_mPYT3PkhgjPw` from `output/live/interview.sqlite`.)

## Candidate consent

I, **Muhammad Taha Farrukh**, consent to recording this interview and to submitting the recording and related interview artifacts for **AI Season FirstRound** grading. National ID, home address, and phone numbers are not to be included in submission materials.
