# Phase 7 test checklist

Do not mark a box unless that test was actually run.

## Architecture

```
LiveKit + Gemini Live interviewer  (unchanged)
            |
            v
   output/live/interview.sqlite
            ^
            |
   src/mcp_server.py  (FastMCP, stdio, read-only)
            |
   MCP client (Claude Desktop — not connected in these checks)
```

MCP is recruiter-side inspection. It is not on the realtime audio path.

## Tools

- `get_interview_status`
- `get_interview_transcript`
- `get_current_question`
- `get_interview_report`
- `list_interviews`
- `get_question_plan`
- `get_github_evidence`

## Setup

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src\mcp_server.py
```

`python src\mcp_server.py` is stdio. The automated suite does **not** leave that process running.

## Test command

```powershell
python src\run_phase7_checks.py
```

## Security restrictions verified offline

- [x] MCP cannot mutate `output/question_plan.json`
- [x] MCP cannot mutate SQLite interview state
- [x] MCP cannot write `output/interview_evaluation.json` / `output/interview_report.json`
- [x] Missing interview ID returns a structured error
- [x] Invalid question ID returns a structured error
- [x] Empty transcript returns `report not available`
- [x] Tools do not return API keys / `.env` secrets
- [x] No LiveKit / Gemini / GitHub API imports on the MCP server
- [x] `agent.py` does not import `mcp_server`

## Automated results

Command: `python src/run_phase7_checks.py`

- [x] Passed **191/191**
- [x] Phase 1–6 regressions included in that run
- [x] FastMCP server object constructed
- [x] All 7 tools registered
- [x] In-process FastMCP `Client` listed tools and called `get_question_plan`
- [x] Approved Taha plan still `sample_mode=false` / `approval_status=approved`
- [x] `get_github_evidence("q8")` returned Conditional-RAG-Uni-Chatbot / `conditional_RAG.py` / SHA `7dcc77e…`

## Not tested in this environment

- [ ] Claude Desktop connected to this MCP server
- [ ] Screenshot of Claude Desktop hammer/tools UI
- [ ] Long-lived `python src/mcp_server.py` stdio session spawned by Claude
- [ ] Live interview started from MCP (intentionally unsupported)

The FastMCP server was constructed and exercised in-process. Claude Desktop was **not** connected.
