from __future__ import annotations

from pathlib import Path

from prep.paths import INPUTS_DIR
from prep.pdf import write_text_pdf

SAMPLE_GITHUB = "https://github.com/langchain-ai"
SAMPLE_GITHUB_USER = "langchain-ai"
SAMPLE_WARNING = "DEVELOPMENT SAMPLE — NOT FOR FINAL SUBMISSION"


def is_sample_github(url_or_user: str) -> bool:
    return SAMPLE_GITHUB_USER in (url_or_user or "").lower()

SAMPLE_JD = """Junior AI Engineer
Northwind Labs, Karachi
0-2 years experience

About the role
Northwind Labs is hiring a Junior AI Engineer to help build internal assistants
and retrieval-augmented tools. You will work with Python, an LLM framework
(LangChain or LangGraph), and production Git/REST workflows.

Must-haves
- Python fundamentals
- An LLM framework: LangChain or LangGraph
- RAG: chunking, embeddings, retrieval quality
- Git and REST APIs
- One shipped project explained end to end

Nice to have
- FastAPI
- Evaluation / faithfulness checks
- Prompt engineering
- SQLite or another lightweight datastore

Responsibilities
- Implement and debug RAG pipelines
- Turn notebooks into small services
- Write clear commit messages and short design notes
- Pair with senior engineers on production incidents

Assessed competencies
- Technical depth
- Decomposition
- Shipping ability
- Debugging
- Communication
"""

SAMPLE_RESUME = """Ayesha Malik
Junior AI Engineer
Lahore, Pakistan
github.com/langchain-ai
ayesha.malik@example.com

SUMMARY
Junior engineer building retrieval-augmented assistants and LangGraph workflows
in Python. Comfortable turning a notebook into a small FastAPI service.

EDUCATION
B.S. Computer Science, FAST-NUCES, 2024
Relevant coursework: Machine Learning, Databases, Software Engineering

EXPERIENCE
AI Engineering Intern, LocalTech — Jun 2024 to May 2025
- Built a retrieval-augmented helpdesk bot with LangChain, embeddings, and Chroma
- Exposed a FastAPI endpoint that returned cited passages with the answer
- Wrote a small evaluation script for answer faithfulness on 40 gold questions
- Used Git pull requests and issue tracking for weekly releases

SKILLS
Python, LangChain, LangGraph, RAG, FastAPI, Git, REST APIs, SQLite,
prompt engineering, debugging, Chroma

PROJECTS
- RAG Helpdesk: LangChain + embeddings over internal support docs
- Interview Graph: LangGraph state machine with a human approval step
- Voice Notes API: FastAPI service wrapping a transcription model

CERTIFICATIONS
DeepLearning.AI LangChain for LLM Application Development
"""


def write_sample_inputs(inputs_dir: Path | None = None) -> tuple[Path, Path]:
    folder = inputs_dir or INPUTS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    jd_path = folder / "jd.txt"
    resume_path = folder / "resume.pdf"
    jd_path.write_text(SAMPLE_JD.strip() + "\n", encoding="utf-8")
    write_text_pdf(resume_path, SAMPLE_RESUME.strip() + "\n")
    return resume_path, jd_path
