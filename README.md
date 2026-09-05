# FirstRound AI

<p align="center">
  <strong>Real-time AI voice interviewer</strong><br/>
  LiveKit · Gemini Live · LangGraph · SQLite · FastMCP
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/></a>
  <a href="#live-interview"><img src="https://img.shields.io/badge/LiveKit-Cloud-1FD5F9?style=for-the-badge&logo=livekit&logoColor=black" alt="LiveKit"/></a>
  <a href="#live-interview"><img src="https://img.shields.io/badge/Gemini-Live-4285F4?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Gemini Live"/></a>
  <a href="#interview-preparation"><img src="https://img.shields.io/badge/LangGraph-Prep-1C3C3C?style=for-the-badge" alt="LangGraph"/></a>
  <a href="#recruiter-mcp"><img src="https://img.shields.io/badge/FastMCP-stdio-FF6B35?style=for-the-badge" alt="FastMCP"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Mode-Voice%20%2B%202D%20face-0E7C66?style=flat-square" alt="Voice + 2D face"/>
  <img src="https://img.shields.io/badge/Barge--in-Supported-2E8B57?style=flat-square" alt="Barge-in"/>
  <img src="https://img.shields.io/badge/HITL-Approve%20%2F%20Edit%20%2F%20Reject-4A90A4?style=flat-square" alt="HITL"/>
  <img src="https://img.shields.io/badge/Graded-3.6%20%2F%20borderline-E6A817?style=flat-square" alt="Graded 3.6 borderline"/>
  <a href="ARCHITECTURE.md"><img src="https://img.shields.io/badge/Docs-Architecture-6C757D?style=flat-square" alt="Architecture"/></a>
  <a href="SUBMISSION.md"><img src="https://img.shields.io/badge/Docs-Submission-6C757D?style=flat-square" alt="Submission"/></a>
  <a href="https://github.com/MTahaFarrukh/AI-Season-Final"><img src="https://img.shields.io/badge/GitHub-AI--Season--Final-181717?style=flat-square&logo=github" alt="GitHub"/></a>
</p>

---

Candidate joins a browser room, speaks with a natural AI interviewer, sees a local **2D face**, and can **interrupt mid-sentence**. Prep runs through LangGraph + recruiter HITL; live turns persist to SQLite; grading emits a PDF scorecard; recruiters query state from **Claude Desktop** via FastMCP.

| | |
|---|---|
| **Course** | AI Season Final — FirstRound |
| **Role demo** | Junior AI Engineer — Northwind Labs |
| **Graded id** | `AJ_mPYT3PkhgjPw` |
| **Result** | partial (9/12) · overall **3.6** · **`borderline`** |

## Table of contents

- [Submission artifacts](#-submission-artifacts)
- [What it does](#-what-it-does)
- [Architecture](#-architecture)
- [Quick start](#-quick-start)
- [Live interview](#-live-interview)
- [Interview preparation](#-interview-preparation)
- [Recruiter MCP](#-recruiter-mcp)
- [Grading](#-grading)
- [Docs](#-docs)

---

## 📦 Submission artifacts

> Screenshots and the graded PDF live in the repo — use these paths for portal / demo proof.

| Artifact | Path |
|----------|------|
| Claude Desktop MCP tools (1) | [`submission/screenshots/claude-mcp-tools-1.png`](submission/screenshots/claude-mcp-tools-1.png) |
| Claude Desktop MCP tools (2) | [`submission/screenshots/claude-mcp-tools-2.png`](submission/screenshots/claude-mcp-tools-2.png) |
| HITL recruiter review (A / E / R) | [`submission/screenshots/hitl-recruiter-review.png`](submission/screenshots/hitl-recruiter-review.png) |
| **Graded recruiter PDF** | **[`output/report.pdf`](output/report.pdf)** |
| Scorecard JSON | [`output/scorecard.json`](output/scorecard.json) |
| Transcript JSON | [`output/transcript.json`](output/transcript.json) |

```text
submission/screenshots/          ← Claude MCP + HITL proof images
output/report.pdf                ← graded recruiter scorecard (open this)
output/scorecard.json
output/transcript.json
```

Prior graded take backup: `output/backup-taha-live-20260814/`.

---

## ✨ What it does

| Area | Capability |
|------|------------|
| **Live voice** | LiveKit Cloud room + Gemini Live interviewer |
| **Presence** | Local 2D face with mouth animation (no vendor avatar) |
| **Barge-in** | Candidate can interrupt; agent stops and listens |
| **Prep** | Resume + JD + GitHub → 12-question plan (LangGraph) |
| **HITL** | Recruiter approve / edit / reject before go-live |
| **Grounding** | GitHub-cited questions from real repo / file / commit |
| **Persist** | SQLite interview store + transcript restore |
| **Grade** | Offline evaluation → scorecard + **`output/report.pdf`** |
| **MCP** | FastMCP stdio tools in Claude Desktop |

---

## 🏗 Architecture

```text
inputs/ (resume, JD, GitHub)
        │
        ▼
 LangGraph prep ──HITL──► output/question_plan.json
        │
        ▼
 LiveKit + Gemini Live ◄── browser (2D face)
        │
        ▼
 SQLite store + transcript
        │
        ├──► evaluate → scorecard.json + report.pdf
        └──► mcp_server.py (stdio) ◄── Claude Desktop
```

More detail: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 🚀 Quick start

### Prerequisites

- Python **3.11+**
- LiveKit Cloud project
- Google AI Studio key with **Gemini Live** access
- Microphone + modern browser

### Environment

Copy `.env.example` → `.env` and fill locally. **Never** paste secrets into chat, logs, videos, or this README.

```env
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
GOOGLE_API_KEY=
GITHUB_TOKEN=
FIRSTROUND_MODE=voice

# SaaS API (optional for legacy live interview)
DATABASE_URL=sqlite:///./output/saas/firstround.db
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000
```

`FIRSTROUND_MODE=voice` is the supported live mode. `GITHUB_TOKEN` is optional (lower rate limit without it).

### Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## SaaS API (Phase 1)

Product API for organizations → jobs → candidates → applications → interviews.  
Does **not** replace the LiveKit / Gemini CLI flow yet. Details: [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md).

### Migrate database

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
alembic upgrade head
```

### Start SaaS API

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) or `GET /health`.

### Seed demo data

```powershell
$env:PYTHONPATH="src"
python src\api\seed.py
```

### Backend tests

```powershell
$env:PYTHONPATH="src"
pytest tests -q
```

---

## Recruiter web app (Phase 2)

Modern Next.js product UI lives in `web/`. The legacy LiveKit candidate room remains in `frontend/` for the existing interview engine.

### Start frontend

```powershell
# Terminal A — API
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="src"
uvicorn api.main:app --reload --port 8000

# Terminal B — Web
cd web
copy .env.local.example .env.local   # if needed
npm install
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Use **Log in** / **Sign up** to enter the Northwind Labs demo workspace (auth is a development placeholder).

### Frontend tests

```powershell
cd web
npm test
```

Docs: [`docs/FRONTEND_ARCHITECTURE.md`](docs/FRONTEND_ARCHITECTURE.md)

---

## 🎙 Live interview

**Terminal 1 — agent**

```powershell
.\.venv\Scripts\Activate.ps1
python src\agent.py start
```

**Terminal 2 — frontend + token server**

```powershell
.\.venv\Scripts\Activate.ps1
python src\token_server.py
```

**Browser**

1. Open [http://127.0.0.1:8080](http://127.0.0.1:8080)
2. Enter the candidate name
3. Click **Join Interview**
4. Allow the microphone

Keep the agent process running; the token server dispatches `firstround-interviewer` into the room.

### Barge-in check

Talk over the AI mid-sentence. You should see:

```text
[TURN] Agent speaking
[TURN] Candidate started speaking
[INTERRUPT] Agent interrupted
[TURN] Listening to candidate
```

### Latency

Logged at runtime (not hardcoded):

```text
[LATENCY] candidate_stop_to_agent_audio_ms=842
```

---

## 📋 Interview preparation

LangGraph pipeline: resume PDF + JD + GitHub → profile → gaps → top repos → 12-question plan → **HITL** → `output/question_plan.json`.

```powershell
.\.venv\Scripts\Activate.ps1
python src\prepare_interview.py --init-samples
python src\prepare_interview.py --resume inputs\resume.pdf --jd inputs\jd.txt --github https://github.com/<candidate>
```

`--github` is required for a real submission. Omitting it uses a sample repo and warns `DEVELOPMENT SAMPLE — NOT FOR FINAL SUBMISSION`.

At recruiter review: **A** approve · **E** edit · **R** reject.

```powershell
python src\prepare_interview.py --thread-id <id> --resume-action approve
python src\prepare_interview.py --thread-id <id> --resume-action reject
python src\prepare_interview.py --thread-id <id> --resume-action edit --edit "q1=New question text"
python src\prepare_interview.py --inspect
python src\prepare_interview.py --auto-approve
```

HITL proof: [`submission/screenshots/hitl-recruiter-review.png`](submission/screenshots/hitl-recruiter-review.png)

---

## 🔌 Recruiter MCP

MCP is **off** the LiveKit / Gemini audio path. It only reads persisted state and plans.

```text
Live interview → SQLite ← mcp_server.py (stdio) ← Claude Desktop
```

```powershell
python src\mcp_server.py
```

**Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json`) — use *your* absolute paths:

```json
{
  "mcpServers": {
    "firstround": {
      "command": "D:/path/to/repo/.venv/Scripts/python.exe",
      "args": ["D:/path/to/repo/src/mcp_server.py"]
    }
  }
}
```

Fully restart Claude after editing. Do not put API keys in the MCP `env` block.

**Proof screenshots:**  
[`claude-mcp-tools-1.png`](submission/screenshots/claude-mcp-tools-1.png) · [`claude-mcp-tools-2.png`](submission/screenshots/claude-mcp-tools-2.png)

**Tools:** `get_candidate`, `get_question_plan`, `save_score`, `get_scorecard`, `list_interviews`, `get_interview_status`, `get_interview_transcript`, `get_current_question`, `get_interview_report`, `get_github_evidence`

Paths are application-fixed; tools do not expose `.env` secrets.

---

## 📊 Grading

After a live take, regenerate the graded trio:

```powershell
.\.venv\Scripts\Activate.ps1
python src\generate_grading_artifacts.py
```

| Output | Description |
|--------|-------------|
| [`output/transcript.json`](output/transcript.json) | Exported turns |
| [`output/scorecard.json`](output/scorecard.json) | Scores + evidence quotes |
| [`output/report.pdf`](output/report.pdf) | Recruiter PDF report |

Current honest result: **`AJ_mPYT3PkhgjPw`** · partial 9/12 · **3.6** · **`borderline`**

Offline integration (no LiveKit):

```powershell
python src\run_phase8_checks.py
```

---

## 📚 Docs

| Doc | Purpose |
|-----|---------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System design & data flow |
| [`SUBMISSION.md`](SUBMISSION.md) | Portal checklist & honest results |
| `PHASE*_TEST.md` | Historical phase checklists |

---

<p align="center">
  <sub>FirstRound AI · AI Season Final · Built with LiveKit, Gemini Live, LangGraph & FastMCP</sub>
</p>
