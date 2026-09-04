# Phase 2 test checklist

Do not mark a box unless that test was actually run.

## Parsing and profile

- [x] Resume PDF parsed
- [x] JD parsed
- [x] Candidate profile created
- [x] Gap analysis generated
- [x] GitHub URL extracted

## GitHub grounding

- [x] GitHub repositories retrieved
- [x] Top 3 relevant projects selected
- [x] GitHub evidence references generated
- [x] GitHub file@commit relationship is valid
- [x] JD ranking does not use hardcoded AI terms
- [x] Real candidate GitHub URL mode works

Selected on the live sample run: `langchain`, `langgraph`, `langsmith-sdk` from `https://github.com/langchain-ai`.

File@commit citations were checked with `GET /repos/{owner}/{repo}/commits?path=<file>` and the cited SHA was present for all 3 GitHub questions.

`--github https://github.com/octocat` selected only `octocat/*` repositories.

A Frontend JD ranking fixture ranked a React repo above a 140k-star LangChain repo.

## Question plan

- [x] Exactly 12 questions generated
- [x] Correct category distribution
- [x] Question validation works
- [x] Conditional edge works
- [x] Question categories match semantic intent
- [x] `source` is always `jd`, `resume`, `github`, or `scenario`

Required counts verified: 4 Technical, 2 Behavioral, 2 Project/GitHub, 2 Scenario, 1 Culture/Values, 1 Closing.

## HITL + checkpoint

- [x] SQLite checkpoint created
- [x] HITL interrupts graph
- [x] Recruiter can approve
- [x] Recruiter can edit
- [x] Recruiter can reject
- [x] Resume after interrupt works
- [x] Final approved plan saved
- [x] Editing a question triggers validation
- [x] An invalid edited question cannot finalize
- [x] Unknown HITL action cannot approve
- [x] Reject changes question content

Live HITL sequence that was executed:

1. Graph paused at `recruiter_review`
2. Resume unknown action → still paused, not finalized
3. Resume `reject` → new planner call, question text changed, paused again
4. Resume banned edit on `q1` (`How old are you?`) → validation failed, not finalized
5. Resume valid edit on `q1` → finalized with edited text
6. Separate thread: resume `approve` → `output/question_plan.json`

## Phase 1 compatibility

- [x] Existing Phase 1 still works

Checked by import/construct, not a new live call.

## How the live check was run

```powershell
python src\run_phase2_checks.py
```

Result: **58/58 passed**.

Previous checklist run was **36/36**.

## Known limits

- Sample inputs still use `langchain-ai`. The CLI and saved plan warn `DEVELOPMENT SAMPLE — NOT FOR FINAL SUBMISSION`. Use `--github https://github.com/<candidate>` for a real submission.
- Semantic category checks are lightweight regex. A Behavioral label can still pass if the text happens to contain a matching word.
- The planner stamps verified repo/file/commit metadata even if the LLM prose mentions a different file.
- Gemini text prep uses `gemini-flash-latest`. Live interview still uses Gemini 2.5 Native Audio.
