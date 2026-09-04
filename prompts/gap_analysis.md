Compare the job requirements with the candidate profile. Ground every claim in the provided JSON. Do not invent candidate experience.

Return JSON only:
{
  "matched_skills": ["..."],
  "missing_skills": ["..."],
  "weak_matches": ["..."],
  "strong_matches": ["..."],
  "experience_gaps": ["..."],
  "recommended_focus": ["..."],
  "notes": ["..."]
}

Rules:
- matched_skills must appear in both JD and resume evidence.
- missing_skills are JD requirements with no resume evidence.
- weak_matches are partial or only mentioned once.
- recommended_focus should be useful interview topics.
- If evidence is thin, say so in notes.

CONTEXT:
{{CONTEXT_JSON}}
