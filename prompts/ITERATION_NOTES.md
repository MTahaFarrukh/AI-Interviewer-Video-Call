# Prompt iteration notes

## parse_resume / parse_jd — v1

First draft asked the model to "infer likely skills." That caused hallucinated tools that were not on the resume. v2 forbids invention and requires empty strings/lists when evidence is missing.

## gap_analysis — v1

An early version treated JD keywords as candidate skills if they were "common for the role." That invented experience. v2 requires matched skills to appear in both JD and resume evidence.

## text model

`gemini-2.5-flash` returned `NOT_FOUND` for our Google AI Studio key. Prep therefore uses `gemini-flash-latest`. The live interviewer is unchanged and still uses `gemini-2.5-flash-native-audio-preview-12-2025`.

## question_planner — v2 hardening

v1 allowed `source=gap_analysis`, technical questions in Behavioral slots, and GitHub citations that stamped the latest repo SHA onto an unrelated file. v2 forces `jd|resume|github|scenario`, semantic category checks, and `GET /commits?path=` evidence.

## question_planner — v1

The first planner wrote generic "tell me about yourself" items and invented GitHub file paths. v2 pins the 12 required slots in code, and the planner may only cite repositories/files/commits supplied in `github_projects`. The graph also stamps real GitHub references after generation so a bad model output cannot invent a SHA.

## live interviewer / scorecard evidence — v2

The real Taha live transcript contains ASR fragments such as "I" and "Bye bye." Mapping the internal 47 / NO_GO score blindly onto a 1–5 PDF scorecard would invent confidence. v2 refuses any competency score unless a candidate quote of at least 12 characters appears verbatim in a candidate turn. Tests cover a valid quote, an invented quote, and a score that cannot survive without evidence.
