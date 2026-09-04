"""Phase 2 LangGraph: JD + resume + GitHub -> 12-question plan -> recruiter HITL."""

from __future__ import annotations

import operator
import sqlite3
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from config import CHECKPOINT_PATH
from nodes.finalize import finalize_plan
from nodes.gap_analysis import gap_analysis
from nodes.github import analyze_github_node, extract_github
from nodes.hitl import recruiter_review
from nodes.ingest import ingest_inputs
from nodes.parse_jd import parse_jd
from nodes.parse_resume import parse_resume
from nodes.profile import build_candidate_profile
from nodes.questions import generate_question_plan
from nodes.validate import validate_question_plan
from prep.paths import ensure_output_dirs


class InterviewPrepState(TypedDict, total=False):
    thread_id: str
    resume_path: str
    jd_path: str
    github_url_override: str
    resume_text: str
    jd_text: str
    resume_extractor: str
    jd_extractor: str
    github_urls_found: list[str]
    resume: dict[str, Any]
    jd: dict[str, Any]
    candidate_profile: dict[str, Any]
    gap_analysis: dict[str, Any]
    github_url: str
    github_username: str
    github_error: str
    github: dict[str, Any]
    github_projects: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    validation: dict[str, Any]
    generation_attempt: int
    recruiter_action: str
    approval_status: str
    edits_made: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]
    final_plan: dict[str, Any]
    finalized: bool
    output_path: str
    sample_mode: bool


def route_after_github_extract(state: InterviewPrepState) -> Literal["analyze_github", "generate_question_plan"]:
    if state.get("github_username") and not state.get("github_error"):
        return "analyze_github"
    return "generate_question_plan"


def route_after_validation(
    state: InterviewPrepState,
) -> Literal["generate_question_plan", "recruiter_review", "finalize_plan"]:
    validation = state.get("validation") or {}
    attempt = int(state.get("generation_attempt") or 0)
    status = state.get("approval_status") or "pending"
    if status == "edited":
        if validation.get("ok"):
            return "finalize_plan"
        return "recruiter_review"
    if not validation.get("ok") and attempt < 3:
        return "generate_question_plan"
    return "recruiter_review"


def route_after_review(
    state: InterviewPrepState,
) -> Literal["generate_question_plan", "validate_question_plan", "finalize_plan", "recruiter_review"]:
    action = state.get("recruiter_action")
    if action == "reject":
        return "generate_question_plan"
    if action == "edit":
        return "validate_question_plan"
    if action == "approve":
        if (state.get("validation") or {}).get("ok"):
            return "finalize_plan"
        return "validate_question_plan"
    return "recruiter_review"


def build_graph(checkpointer: SqliteSaver):
    builder = StateGraph(InterviewPrepState)
    builder.add_node("ingest_inputs", ingest_inputs)
    builder.add_node("parse_resume", parse_resume)
    builder.add_node("parse_jd", parse_jd)
    builder.add_node("build_candidate_profile", build_candidate_profile)
    builder.add_node("gap_analysis", gap_analysis)
    builder.add_node("extract_github", extract_github)
    builder.add_node("analyze_github", analyze_github_node)
    builder.add_node("generate_question_plan", generate_question_plan)
    builder.add_node("validate_question_plan", validate_question_plan)
    builder.add_node("recruiter_review", recruiter_review)
    builder.add_node("finalize_plan", finalize_plan)

    builder.add_edge(START, "ingest_inputs")
    builder.add_edge("ingest_inputs", "parse_resume")
    builder.add_edge("parse_resume", "parse_jd")
    builder.add_edge("parse_jd", "build_candidate_profile")
    builder.add_edge("build_candidate_profile", "gap_analysis")
    builder.add_edge("gap_analysis", "extract_github")
    builder.add_conditional_edges(
        "extract_github",
        route_after_github_extract,
        {
            "analyze_github": "analyze_github",
            "generate_question_plan": "generate_question_plan",
        },
    )
    builder.add_edge("analyze_github", "generate_question_plan")
    builder.add_edge("generate_question_plan", "validate_question_plan")
    builder.add_conditional_edges(
        "validate_question_plan",
        route_after_validation,
        {
            "generate_question_plan": "generate_question_plan",
            "recruiter_review": "recruiter_review",
            "finalize_plan": "finalize_plan",
        },
    )
    builder.add_conditional_edges(
        "recruiter_review",
        route_after_review,
        {
            "generate_question_plan": "generate_question_plan",
            "validate_question_plan": "validate_question_plan",
            "finalize_plan": "finalize_plan",
            "recruiter_review": "recruiter_review",
        },
    )
    builder.add_edge("finalize_plan", END)
    return builder.compile(checkpointer=checkpointer)


def open_checkpointer() -> tuple[SqliteSaver, sqlite3.Connection]:
    ensure_output_dirs()
    conn = sqlite3.connect(str(CHECKPOINT_PATH), check_same_thread=False)
    return SqliteSaver(conn), conn


def compile_prep_graph():
    checkpointer, conn = open_checkpointer()
    return build_graph(checkpointer), conn
