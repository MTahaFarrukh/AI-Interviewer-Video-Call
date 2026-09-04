"""Post-interview structured evaluation. Never runs on the audio path."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from realtime.evaluate import _COMMIT_RE, _FILE_RE, classify_answer

DIMENSIONS = (
    "jd_resume_fit",
    "technical_competence",
    "problem_solving",
    "communication",
    "project_understanding",
    "github_credibility",
    "overall_interview",
)

# Interview evaluation recommendation — not an irreversible hiring decision.
GO_MIN_OVERALL = 70
GO_MIN_FIT = 60
GO_MIN_TECH = 60
GO_MIN_GITHUB = 50
NO_GO_FIT = 40
NO_GO_TECH = 40
REVIEW_MIN_OVERALL = 50

_LABEL_ASSESSMENT = {
    "strong": "strong",
    "adequate": "adequate",
    "shallow": "weak",
    "off_topic": "weak",
    "bluff": "unsupported",
}
_LABEL_SCORE = {
    "strong": 88,
    "adequate": 72,
    "shallow": 42,
    "off_topic": 28,
    "bluff": 18,
}


def _clamp(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _questions_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in plan.get("questions") or []:
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = item
    return out


def _approved_github_refs(plan: dict[str, Any]) -> dict[str, set[str]]:
    files: set[str] = set()
    commits: set[str] = set()
    repos: set[str] = set()
    for question in _questions_by_id(plan).values():
        if question.get("file"):
            files.add(str(question["file"]).replace("\\", "/").lower())
        if question.get("commit"):
            commits.add(str(question["commit"]).lower())
        if question.get("repository"):
            repos.add(str(question["repository"]).lower())
    for project in plan.get("github_projects") or []:
        if not isinstance(project, dict):
            continue
        if project.get("file_path"):
            files.add(str(project["file_path"]).replace("\\", "/").lower())
        if project.get("commit_sha"):
            commits.add(str(project["commit_sha"]).lower())
        if project.get("url"):
            repos.add(str(project["url"]).lower())
        for file_info in project.get("files") or []:
            if isinstance(file_info, dict) and file_info.get("path"):
                files.add(str(file_info["path"]).replace("\\", "/").lower())
        for commit in project.get("commits") or []:
            if isinstance(commit, dict) and commit.get("sha"):
                commits.add(str(commit["sha"]).lower())
    return {"files": files, "commits": commits, "repos": repos}


def _gap(plan: dict[str, Any], gap: dict[str, Any] | None) -> dict[str, Any]:
    if gap:
        return gap
    embedded = plan.get("gap_analysis")
    return embedded if isinstance(embedded, dict) else {}


def _jd_fit_score(gap: dict[str, Any]) -> int:
    matched = len(gap.get("matched_skills") or [])
    missing = len(gap.get("missing_skills") or [])
    weak = len(gap.get("weak_matches") or [])
    denom = matched + missing + 0.5 * weak
    if denom <= 0:
        return 55
    return _clamp(100.0 * matched / denom)


def _combine_labels(labels: list[str]) -> str:
    if not labels:
        return "shallow"
    if "bluff" in labels:
        return "bluff"
    if "strong" in labels:
        return "strong"
    if "adequate" in labels:
        return "adequate"
    if labels and all(item == "off_topic" for item in labels):
        return "off_topic"
    return "shallow"


def _github_claim_status(text: str, refs: dict[str, set[str]]) -> str:
    claimed_files = [m.group(0).replace("\\", "/").lower() for m in _FILE_RE.finditer(text)]
    claimed_commits = [m.group(0).lower() for m in _COMMIT_RE.finditer(text)]
    if not claimed_files and not claimed_commits:
        return "none"
    file_ok = True
    commit_ok = True
    if claimed_files:
        file_ok = any(
            any(path in approved or approved in path for approved in refs["files"])
            for path in claimed_files
        ) if refs["files"] else False
    if claimed_commits:
        commit_ok = any(
            any(item in approved or approved.startswith(item) for approved in refs["commits"])
            for item in claimed_commits
        ) if refs["commits"] else False
    if file_ok and commit_ok:
        return "supported"
    if (claimed_files and file_ok) or (claimed_commits and commit_ok):
        return "partially_supported"
    return "unsupported"


def _answers_by_question(transcript: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for turn in transcript:
        if turn.get("speaker") != "candidate" or turn.get("turn_type") != "answer":
            continue
        qid = str(turn.get("question_id") or "").strip()
        text = str(turn.get("text") or "").strip()
        if qid and text:
            grouped[qid].append(text)
    return grouped


def recommend(dimensions: dict[str, int], concerns: list[str]) -> tuple[str, str]:
    """Deterministic GO / NO_GO / REVIEW rule. Configurable via module constants."""
    overall = dimensions.get("overall_interview", 0)
    fit = dimensions.get("jd_resume_fit", 0)
    tech = dimensions.get("technical_competence", 0)
    github = dimensions.get("github_credibility", 0)
    serious = any(
        "unsupported" in item.lower()
        or "contradict" in item.lower()
        or "bluff" in item.lower()
        or "credibility" in item.lower()
        for item in concerns
    )
    if fit < NO_GO_FIT or tech < NO_GO_TECH or serious:
        return (
            "NO_GO",
            "Poor JD fit, major technical gaps, or serious unsupported project claims.",
        )
    if (
        overall >= GO_MIN_OVERALL
        and fit >= GO_MIN_FIT
        and tech >= GO_MIN_TECH
        and github >= GO_MIN_GITHUB
        and not serious
    ):
        return (
            "GO",
            "Strong overall fit, acceptable technical performance, and no major credibility concerns.",
        )
    if overall < REVIEW_MIN_OVERALL:
        return (
            "NO_GO",
            "Interview performance is below the review band.",
        )
    return (
        "REVIEW",
        "Mixed or borderline evidence; not enough to recommend GO or NO_GO.",
    )


def evaluate_interview(
    plan: dict[str, Any],
    transcript: list[dict[str, Any]],
    *,
    profile: dict[str, Any] | None = None,
    gap: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a completed transcript. Does not mutate the live controller."""
    questions = _questions_by_id(plan)
    gap_data = _gap(plan, gap)
    refs = _approved_github_refs(plan)
    answers = _answers_by_question(transcript)
    asked: list[str] = []
    for turn in transcript:
        qid = str(turn.get("question_id") or "").strip()
        if qid and qid not in asked:
            asked.append(qid)
    if not asked:
        asked = list(questions.keys())
    question_results: list[dict[str, Any]] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    concerns: list[str] = []
    evidence: list[str] = []
    github_scores: list[int] = []
    tech_scores: list[int] = []
    problem_scores: list[int] = []
    project_scores: list[int] = []
    comm_flags: list[int] = []

    for qid in asked:
        question = questions.get(qid) or {"id": qid, "category": ""}
        texts = answers.get(qid) or []
        labels = [classify_answer(text, question) for text in texts]
        combined = _combine_labels(labels)
        assessment = _LABEL_ASSESSMENT[combined]
        score = _LABEL_SCORE[combined]
        if not texts:
            assessment = "weak"
            score = 35
            labels = ["shallow"]
        q_evidence = []
        q_concerns = []
        blob = " ".join(texts)
        status = _github_claim_status(blob, refs)
        if status == "unsupported":
            q_concerns.append("Unsupported GitHub/file/commit claim versus the approved plan.")
            concerns.append(f"{qid}: unsupported GitHub or implementation claim.")
            assessment = "unsupported"
            score = min(score, 18)
            combined = "bluff"
        elif status == "supported":
            q_evidence.append("Claimed file or commit matches approved GitHub evidence.")
        elif status == "partially_supported":
            q_evidence.append("Some GitHub details match the approved plan.")
        if combined == "strong":
            q_evidence.append("Concrete implementation detail and reasoning in the exchange.")
            strengths.append(f"{qid}: strong, specific explanation.")
        elif combined == "adequate":
            q_evidence.append("Directly addressed the question with reasonable detail.")
        elif combined == "shallow":
            q_concerns.append("Repeated or vague answers with little evidence.")
            weaknesses.append(f"{qid}: shallow or under-specified answers.")
        elif combined == "off_topic":
            q_concerns.append("Did not address the current question.")
            weaknesses.append(f"{qid}: off-topic response.")
        category = str(question.get("category") or "")
        source = str(question.get("source") or question.get("source_type") or "")
        question_results.append(
            {
                "question_id": qid,
                "category": category,
                "answer_summary": (blob[:280] + "…") if len(blob) > 280 else blob,
                "assessment": assessment,
                "evidence": q_evidence,
                "concerns": q_concerns,
                "score": score,
            }
        )
        evidence.extend(q_evidence)
        if source == "github" or "github" in category.lower() or question.get("file"):
            github_scores.append(score)
        if "technical" in category.lower() or str(question.get("competency") or "").lower() in {
            "technical depth",
            "debugging",
            "shipping ability",
        }:
            tech_scores.append(score)
        if "scenario" in category.lower() or "debug" in str(question.get("competency") or "").lower():
            problem_scores.append(score)
        if "project" in category.lower() or question.get("project"):
            project_scores.append(score)
        comm_flags.append(80 if combined in {"strong", "adequate"} else 40 if combined == "shallow" else 25)

    fit = _jd_fit_score(gap_data)
    if gap_data.get("strong_matches"):
        strengths.append("Phase 2 gap analysis shows strong skill matches with the JD.")
        evidence.append("Approved gap analysis strong matches were reused; the prep graph was not rerun.")
    if gap_data.get("missing_skills"):
        weaknesses.append("JD skills are missing from the approved profile.")
    if gap_data.get("weak_matches"):
        weaknesses.append("Some JD skills are only weakly evidenced on the resume.")

    interview_avg = _clamp(
        sum(item["score"] for item in question_results) / max(len(question_results), 1)
    )
    dimensions = {
        "jd_resume_fit": fit,
        "technical_competence": _clamp(sum(tech_scores) / len(tech_scores)) if tech_scores else interview_avg,
        "problem_solving": _clamp(sum(problem_scores) / len(problem_scores)) if problem_scores else interview_avg,
        "communication": _clamp(sum(comm_flags) / len(comm_flags)) if comm_flags else 50,
        "project_understanding": _clamp(sum(project_scores) / len(project_scores)) if project_scores else interview_avg,
        "github_credibility": _clamp(sum(github_scores) / len(github_scores)) if github_scores else (70 if refs["files"] else 55),
        "overall_interview": interview_avg,
    }
    if any("unsupported" in item.lower() for item in concerns):
        dimensions["github_credibility"] = min(dimensions["github_credibility"], 25)
    overall = _clamp(
        0.20 * dimensions["jd_resume_fit"]
        + 0.20 * dimensions["technical_competence"]
        + 0.15 * dimensions["problem_solving"]
        + 0.10 * dimensions["communication"]
        + 0.15 * dimensions["project_understanding"]
        + 0.10 * dimensions["github_credibility"]
        + 0.10 * dimensions["overall_interview"]
    )
    rec, reason = recommend(dimensions, concerns)
    candidate = plan.get("candidate") or {}
    job = plan.get("job") or {}
    profile = profile or {}
    name = str(candidate.get("name") or profile.get("name") or "").strip()
    return {
        "candidate": {
            "name": name,
            "role": str(job.get("role") or "").strip(),
            "company": str(job.get("company") or "").strip(),
        },
        "overall_score": overall,
        "dimensions": dimensions,
        "question_results": question_results,
        "strengths": strengths[:8],
        "weaknesses": weaknesses[:8],
        "concerns": concerns[:8],
        "evidence": evidence[:8],
        "recommendation": rec,
        "recommendation_reason": reason,
        "thresholds": {
            "GO_MIN_OVERALL": GO_MIN_OVERALL,
            "GO_MIN_FIT": GO_MIN_FIT,
            "GO_MIN_TECH": GO_MIN_TECH,
            "GO_MIN_GITHUB": GO_MIN_GITHUB,
            "NO_GO_FIT": NO_GO_FIT,
            "NO_GO_TECH": NO_GO_TECH,
            "REVIEW_MIN_OVERALL": REVIEW_MIN_OVERALL,
        },
    }
