from __future__ import annotations

import json
from typing import Any

from prep.banned import SAFE_REPLACEMENT_QUESTION, banned_hits
from prep.llm import LlmError, generate_json
from prep.paths import PROMPTS_DIR
from prep.question_quality import (
    behavioral_contamination_issue,
    flatten_source_reference,
    match_question_to_project,
    normalize_source,
    semantic_issue,
    short_project_name,
    speakability_issue,
)

REQUIRED_CATEGORIES: tuple[tuple[str, int], ...] = (
    ("Technical", 4),
    ("Behavioral", 2),
    ("Project/GitHub", 2),
    ("Scenario", 2),
    ("Culture/Values", 1),
    ("Closing", 1),
)

QUESTION_SLOTS: list[dict[str, str]] = [
    {"id": "q1", "category": "Technical", "source": "jd"},
    {"id": "q2", "category": "Technical", "source": "jd"},
    {"id": "q3", "category": "Technical", "source": "resume"},
    {"id": "q4", "category": "Technical", "source": "github"},
    {"id": "q5", "category": "Behavioral", "source": "resume"},
    {"id": "q6", "category": "Behavioral", "source": "jd"},
    {"id": "q7", "category": "Project/GitHub", "source": "github"},
    {"id": "q8", "category": "Project/GitHub", "source": "github"},
    {"id": "q9", "category": "Scenario", "source": "scenario"},
    {"id": "q10", "category": "Scenario", "source": "scenario"},
    {"id": "q11", "category": "Culture/Values", "source": "jd"},
    {"id": "q12", "category": "Closing", "source": "jd"},
]


def plan_questions(
    *,
    profile: dict[str, Any],
    jd: dict[str, Any],
    gaps: dict[str, Any],
    github: dict[str, Any],
    attempt: int,
) -> list[dict[str, Any]]:
    template = (PROMPTS_DIR / "question_planner.md").read_text(encoding="utf-8")
    context = {
        "candidate": profile,
        "job": {k: v for k, v in jd.items() if k != "raw_text"},
        "gap_analysis": gaps,
        "github_projects": github.get("projects") or [],
        "github_error": github.get("error") or "",
        "attempt": attempt,
        "required_slots": QUESTION_SLOTS,
    }
    prompt = template.replace("{{CONTEXT_JSON}}", json.dumps(context, indent=2)[:18000])
    try:
        data = generate_json(prompt, temperature=0.35)
        raw_questions = data.get("questions") if isinstance(data, dict) else data
        if not isinstance(raw_questions, list):
            raise LlmError("Question planner did not return a questions list")
    except LlmError:
        raw_questions = []
    merged = _merge_slots(raw_questions)
    return _stamp_real_references(merged, profile, jd, gaps, github)


def _merge_slots(raw_questions: list[Any]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or "").strip()
        category = str(item.get("category") or "").strip()
        cleaned = _normalize_question(item)
        if qid:
            by_id[qid] = cleaned
        if category:
            by_category.setdefault(category, []).append(cleaned)

    questions: list[dict[str, Any]] = []
    used_texts: set[str] = set()
    for slot in QUESTION_SLOTS:
        chosen = by_id.get(slot["id"])
        if not chosen:
            pool = by_category.get(slot["category"]) or []
            chosen = pool.pop(0) if pool else {}
        text = str(chosen.get("question") or chosen.get("text") or "").strip()
        if text.lower() in used_texts:
            text = ""
        if text:
            used_texts.add(text.lower())
        merged = {
            **slot,
            **chosen,
            "id": slot["id"],
            "category": slot["category"],
            "source": chosen.get("source") or slot["source"],
            "question": text,
            "text": text,
        }
        questions.append(_normalize_question(merged))
    return questions


def _normalize_question(item: dict[str, Any]) -> dict[str, Any]:
    text = str(item.get("question") or item.get("text") or "").strip()
    return {
        "id": str(item.get("id") or "").strip(),
        "category": str(item.get("category") or "").strip(),
        "question": text,
        "text": text,
        "competency": str(item.get("competency") or "").strip(),
        "gap_context": str(item.get("gap_context") or "").strip(),
        "difficulty": _difficulty(item.get("difficulty")),
        "rationale": str(item.get("rationale") or "").strip(),
        "expected_evidence": str(item.get("expected_evidence") or "").strip(),
        "source": normalize_source(
            str(item.get("source") or item.get("source_type") or ""),
            str(item.get("category") or ""),
        ),
        "source_type": normalize_source(
            str(item.get("source") or item.get("source_type") or ""),
            str(item.get("category") or ""),
        ),
        "source_url": str(item.get("source_url") or "").strip(),
        "source_reference": flatten_source_reference(item.get("source_reference")),
        "project": str(item.get("project") or "").strip(),
        "repository": str(item.get("repository") or "").strip(),
        "file": str(item.get("file") or "").strip(),
        "commit": str(item.get("commit") or "").strip(),
        "evidence": str(item.get("evidence") or "").strip(),
        "follow_up_triggers": [
            str(x).strip() for x in (item.get("follow_up_triggers") or []) if str(x).strip()
        ],
        "banned_flags": banned_hits(text),
    }


def _difficulty(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    if text in {"easy", "medium", "hard"}:
        return text
    return "medium"


def _stamp_real_references(
    questions: list[dict[str, Any]],
    profile: dict[str, Any],
    jd: dict[str, Any],
    gaps: dict[str, Any],
    github: dict[str, Any],
) -> list[dict[str, Any]]:
    projects = list(github.get("projects") or [])
    github_slots = [
        q
        for q in questions
        if q["category"] == "Project/GitHub" or q["id"] == "q4" or q.get("source") == "github"
    ]
    used_names: set[str] = set()
    for question in github_slots:
        project, preferred_file = match_question_to_project(question, projects)
        if project is None:
            project = next(
                (item for item in projects if str(item.get("name") or "") not in used_names),
                projects[0] if projects else None,
            )
            if project is not None:
                question["question"] = _fallback_github_question(project)
                question["text"] = question["question"]
                preferred_file = str(project.get("file_path") or "")
        if project is None:
            continue
        used_names.add(str(project.get("name") or ""))
        question.update(_project_reference(project, preferred_file))
        question["source"] = "github"
        question["source_type"] = "github"
        if (
            semantic_issue(question)
            or speakability_issue(question)
            or match_question_to_project(question, projects)[0] is None
        ):
            question["question"] = _fallback_github_question(project, question.get("file"))
            question["text"] = question["question"]
        if not question.get("competency"):
            question["competency"] = "github_grounding"
        if not question.get("rationale"):
            question["rationale"] = project.get("why_relevant") or "Grounded in a retrieved repository."
        if not question.get("expected_evidence"):
            question["expected_evidence"] = (
                "Candidate walks through the cited file or commit using their own words."
            )

    for question in questions:
        question["source"] = normalize_source(question.get("source") or "", question.get("category") or "")
        question["source_type"] = question["source"]
        question["source_reference"] = flatten_source_reference(question.get("source_reference"))
        if gaps:
            question["gap_context"] = question.get("gap_context") or "; ".join(
                (gaps.get("recommended_focus") or [])[:2]
            )
        if question["source"] == "github" and question.get("repository"):
            question["banned_flags"] = banned_hits(question.get("question") or "")
            if question["banned_flags"]:
                question["guardrail_flags"] = [
                    {"type": "banned_question", "categories": list(question["banned_flags"])}
                ]
                question["question"] = SAFE_REPLACEMENT_QUESTION
                question["text"] = question["question"]
                question["banned_flags"] = banned_hits(question.get("question") or "")
            continue
        if question["category"] == "Behavioral":
            question["source"] = "resume" if (profile.get("projects") or profile.get("experience")) else "jd"
            question["source_type"] = question["source"]
            question["source_reference"] = question["source_reference"] or (
                "resume.projects: " + short_project_name(str((profile.get("projects") or ["a recent project"])[0]))
            )
        elif question["source"] == "resume" and profile.get("experience"):
            question["source_reference"] = question["source_reference"] or (
                "resume.experience: " + short_project_name(str(profile["experience"][0]))
            )
        elif question["source"] == "scenario":
            skill = (jd.get("required_skills") or ["role requirements"])[0]
            question["source_reference"] = question["source_reference"] or f"jd.required_skills: {skill}"
        else:
            skill = (jd.get("required_skills") or ["role requirements"])[0]
            question["source"] = question["source"] if question["source"] in {"jd", "resume"} else "jd"
            question["source_type"] = question["source"]
            question["source_reference"] = question["source_reference"] or f"jd.required_skills: {skill}"
        dirty = (
            not question.get("question")
            or semantic_issue(question)
            or speakability_issue(question)
            or behavioral_contamination_issue(question, profile)
        )
        if dirty:
            question["question"] = _fallback_text(question, jd, profile, gaps)
            question["text"] = question["question"]
        question["banned_flags"] = banned_hits(question.get("question") or "")
        if question["banned_flags"]:
            question["guardrail_flags"] = [
                {"type": "banned_question", "categories": list(question["banned_flags"])}
            ]
            question["question"] = SAFE_REPLACEMENT_QUESTION
            question["text"] = question["question"]
            question["banned_flags"] = banned_hits(question.get("question") or "")
    return questions


def _project_reference(project: dict[str, Any], file_path: str | None = None) -> dict[str, str]:
    sha = str(project.get("commit_sha") or "") if project.get("commit_verified") else ""
    path = str(file_path or project.get("file_path") or project.get("readme_path") or "").replace("\\", "/")
    allowed = [
        str(project.get("file_path") or "").replace("\\", "/"),
        str(project.get("readme_path") or "").replace("\\", "/"),
    ]
    for item in project.get("files") or []:
        if isinstance(item, dict) and item.get("path"):
            allowed.append(str(item["path"]).replace("\\", "/"))
    allowed = [item for item in allowed if item]
    if path and allowed and path not in allowed:
        path = str(project.get("file_path") or allowed[0])
    full = str(project.get("full_name") or project.get("name") or "")
    reference = full
    if path:
        reference += f"/{path}"
    if sha and path:
        reference += f"@{sha[:7]}"
    elif sha and not path:
        sha = ""
    owner_repo = full
    source_url = str(project.get("source_url") or "")
    if path and sha and owner_repo:
        source_url = f"https://github.com/{owner_repo}/blob/{sha}/{path}"
    return {
        "project": str(project.get("name") or ""),
        "repository": str(project.get("url") or ""),
        "file": path,
        "commit": sha,
        "source_url": source_url,
        "evidence": str(project.get("evidence") or project.get("readme_excerpt") or "")[:500],
        "source_reference": reference,
    }


def _fallback_github_question(project: dict[str, Any], file_path: str | None = None) -> str:
    name = project.get("name") or "this repository"
    path = file_path or project.get("file_path") or project.get("readme_path") or "the README"
    return (
        f"Walk me through {path} in {name}. What problem does that code solve, "
        "and what would you change if you had to ship it again?"
    )


def _skill_phrase(raw: Any) -> str:
    text = str(raw or "").strip()
    if ":" in text:
        after = text.split(":", 1)[1].strip()
        if after:
            return after
    return text or "the core skills"


def _fallback_text(
    question: dict[str, Any],
    jd: dict[str, Any],
    profile: dict[str, Any],
    gaps: dict[str, Any],
) -> str:
    role = jd.get("role") or "this role"
    skills = jd.get("required_skills") or profile.get("skills") or ["the core skills"]
    skill = _skill_phrase(skills[0])
    skill_b = _skill_phrase(skills[1] if len(skills) > 1 else skills[0])
    projects = profile.get("projects") or ["a recent project"]
    project = short_project_name(str(projects[0]))
    project_b = short_project_name(str(projects[1] if len(projects) > 1 else projects[0]))
    by_id = {
        "q1": f"For the {role} role, how have you used {skill} in a real project, and what broke first?",
        "q2": f"Walk me through how you would measure retrieval quality for {skill_b}. What metric would you trust?",
        "q3": f"On your resume you mention {project}. What was the hardest technical decision in that work?",
        "q5": (
            f"Tell me about a time you had to deliver {project} under a tight deadline. "
            "What did you prioritize, and what trade-offs did you make?"
        ),
        "q6": (
            f"Describe a time you disagreed with a teammate or a review comment while building {project_b}. "
            "How did you handle it?"
        ),
        "q9": f"Imagine a {role} assistant returns a fluent but wrong answer. How would you debug that path?",
        "q10": f"Suppose you have one day to turn a notebook using {skill} into a small API. What would you cut and what would you keep?",
        "q11": f"This team values shipping and honest debugging. How do you approach asking for help when you are stuck?",
        "q12": f"What is one question you want to ask us about the {role} work, and why does it matter to you?",
    }
    return by_id.get(question["id"], f"Tell me how you would approach the {role} work.")
