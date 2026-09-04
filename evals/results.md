# Persona eval results

These transcripts are synthetic. They were scored with the existing offline evaluator,
then mapped through the PDF scorecard adapter. Rankings were not hardcoded.

| Persona | Score (1–5) | Legacy 0–100 | Recommendation | Confidence | Rank | Expected |
|---|---:|---:|---|---:|---:|---|
| nervous | 4.6 | 82 | hire | 1.0 | 1 | Pauses, restarts, and apologizes, but the completed answer is technically specific and should land near Strong. |
| strong | 4.6 | 83 | hire | 1.0 | 2 | Specific numbers, trade-offs, accurate project/code references, admits one real gap, sharp closing question. |
| average | 3.8 | 72 | borderline | 1.0 | 3 | Correct but generic answers with thin specifics. |
| bluffer | 2.4 | 47 | no_hire | 1.0 | 4 | Fluent and confident, then collapses on specifics and claims GitHub work that is not in the approved evidence. |
| weak | 2.0 | 40 | no_hire | 1.0 | 5 | Vague, cannot explain the project, confuses basic terms. |

## Actual vs expected

### strong

- Expected rank/behavior: highest — Specific numbers, trade-offs, accurate project/code references, admits one real gap, sharp closing question.
- Actual: score=4.6 recommendation=hire confidence=1.0 rank=2
- Legacy evaluator: 83 / GO

### average

- Expected rank/behavior: middle — Correct but generic answers with thin specifics.
- Actual: score=3.8 recommendation=borderline confidence=1.0 rank=3
- Legacy evaluator: 72 / REVIEW

### weak

- Expected rank/behavior: lowest — Vague, cannot explain the project, confuses basic terms.
- Actual: score=2.0 recommendation=no_hire confidence=1.0 rank=5
- Legacy evaluator: 40 / NO_GO

### bluffer

- Expected rank/behavior: below_average — Fluent and confident, then collapses on specifics and claims GitHub work that is not in the approved evidence.
- Actual: score=2.4 recommendation=no_hire confidence=1.0 rank=4
- Legacy evaluator: 47 / NO_GO

### nervous

- Expected rank/behavior: near_strong — Pauses, restarts, and apologizes, but the completed answer is technically specific and should land near Strong.
- Actual: score=4.6 recommendation=hire confidence=1.0 rank=1
- Legacy evaluator: 82 / GO

## Failures / limitations

- Ranking checks passed for this synthetic set.

- Scorecard overall is the mean of evidence-gated 1–5 competency scores, not a raw 0–100 dump.
- JD/resume fit is not scored from gap analysis alone; it needs a candidate quote.
- These personas are not the live Taha interview.
