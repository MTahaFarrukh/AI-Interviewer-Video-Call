# Phase 8 test checklist

Offline integration hardening. Does not start LiveKit or consume Gemini Live minutes.

## Demo path verified

approved Taha plan → transcript → SQLite store → evaluator → recruiter report → MCP read-only inspection

## Test command

```powershell
python src\run_phase8_checks.py
```

## Automated results

- [x] Passed **207/207**
- [x] Approved plan is Muhammad Taha Farrukh / Junior AI Engineer / Northwind Labs
- [x] `sample_mode=false`, 12 questions
- [x] On-disk transcript evaluates and generates a report
- [x] Evaluation/report candidate/role/company match the approved plan
- [x] SQLite store can load a persisted interview
- [x] MCP can read status, transcript, and report
- [x] MCP does not mutate the plan or store
- [x] No Ayesha / `github.com/langchain-ai` sample data in final artifacts
- [x] Phase 1–7 regressions included in the same run
- [x] Gemini model, LiveKit audio path, and scoring thresholds unchanged

## Not run

- [ ] Live LiveKit / Gemini interview
- [ ] Claude Desktop MCP session
