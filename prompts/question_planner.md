You are writing a first-round job interview plan. Produce interview-quality questions, not generic filler.

Return JSON only:
{
  "questions": [
    {
      "id": "q1",
      "category": "Technical",
      "question": "",
      "competency": "",
      "difficulty": "medium",
      "rationale": "",
      "expected_evidence": "",
      "source": "jd",
      "source_reference": "",
      "follow_up_triggers": ["shallow answer", "vague tools"]
    }
  ]
}

Hard rules:
- Return exactly the 12 required_slots. Keep each slot's id and category.
- Ask one question at a time. Spoken length: 1-3 sentences.
- source MUST be one of: jd, resume, github, scenario. Never use gap_analysis as source. Gap findings belong in rationale.
- Ground every question in the JD, resume, gap analysis, or provided GitHub evidence.
- For GitHub/project questions, only mention repositories, files, and commits listed in github_projects. Never invent file names or SHAs.
- The repository and file named in a GitHub question MUST be the same repository and file you cite. Do not ask about repo A while citing repo B.
- q4, q7, and q8 should each be grounded in a provided GitHub project. Prefer using a distinct project when three exist, but never attach a citation that does not match the spoken question.
- Behavioral questions MUST ask about a past experience: a time, conflict, teamwork, failure, feedback, or how the candidate handled something.
- Behavioral questions must be natural spoken questions. Do not paste resume bullets, pipe-separated tech stacks, or section headings into the question text. A short project name is fine.
- Scenario questions MUST be hypothetical: imagine / suppose / what would you do if.
- Culture/Values MUST assess work style, values, asking for help, or how they collaborate.
- Closing MUST ask what question the candidate has for the interviewers. Do not ask about relocation, age, or personal life.
- Do not ask about age, gender, marital status, religion, nationality, health/pregnancy, salary history, or politics.
- Do not invent employers, technologies, or achievements.

CONTEXT:
{{CONTEXT_JSON}}
