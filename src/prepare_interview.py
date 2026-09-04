"""CLI for the Phase 2 interview-preparation graph."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from langgraph.types import Command

from config import CHECKPOINT_PATH, QUESTION_PLAN_PATH, load_prep_settings
from graph import compile_prep_graph
from plan_loader import describe_loaded_plan, load_approved_plan
from prep.paths import INPUTS_DIR
from prep.samples import SAMPLE_WARNING, is_sample_github, write_sample_inputs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("firstround.prep")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a FirstRound interview question plan")
    parser.add_argument("--resume", help="Path to resume PDF")
    parser.add_argument("--jd", help="Path to job description (.txt or .pdf)")
    parser.add_argument(
        "--github",
        default="",
        help="Candidate GitHub URL, e.g. https://github.com/<candidate>. "
        "Required for a real submission. The sample langchain-ai org is development only.",
    )
    parser.add_argument("--thread-id", default="", help="Stable LangGraph thread id")
    parser.add_argument(
        "--resume-action",
        choices=["approve", "edit", "reject"],
        help="Resume a paused recruiter review",
    )
    parser.add_argument("--edit", action="append", default=[], help="Edit as id=new question text")
    parser.add_argument("--reason", default="", help="Optional reject reason")
    parser.add_argument("--auto-approve", action="store_true", help="Approve at the HITL gate without a prompt")
    parser.add_argument("--inspect", action="store_true", help="Print the saved question plan")
    parser.add_argument("--init-samples", action="store_true", help="Write sample JD and resume inputs")
    args = parser.parse_args(argv)

    if args.init_samples:
        resume_path, jd_path = write_sample_inputs()
        print(f"Wrote {resume_path}")
        print(f"Wrote {jd_path}")
        return 0

    if args.inspect:
        return _inspect()

    load_prep_settings()
    resume_path = Path(args.resume) if args.resume else INPUTS_DIR / "resume.pdf"
    jd_path = Path(args.jd) if args.jd else INPUTS_DIR / "jd.txt"
    real_github = bool(args.github) and not is_sample_github(args.github)
    if not resume_path.is_file() or not jd_path.is_file():
        if real_github:
            print(
                "Real GitHub URL provided but resume/JD is missing. "
                "Refusing to fall back to sample inputs.",
                file=sys.stderr,
            )
            return 1
        write_sample_inputs()
        print("Sample inputs were missing, so they were created in inputs/.")
        resume_path = INPUTS_DIR / "resume.pdf"
        jd_path = INPUTS_DIR / "jd.txt"

    graph, conn = compile_prep_graph()
    try:
        thread_id = args.thread_id or f"prep-{uuid.uuid4().hex[:10]}"
        config = {"configurable": {"thread_id": thread_id}}
        if args.resume_action:
            result = graph.invoke(_resume_command(args), config)
        else:
            payload = {
                "thread_id": thread_id,
                "resume_path": str(resume_path),
                "jd_path": str(jd_path),
                "github_url_override": args.github,
            }
            logger.info("[PREP] starting thread_id=%s", thread_id)
            if args.github:
                logger.info("[PREP] using candidate GitHub override")
            if not args.github or is_sample_github(args.github):
                logger.warning(SAMPLE_WARNING)
            result = graph.invoke(payload, config)

        if _is_interrupted(graph, config, result):
            _print_review(graph, config)
            if args.auto_approve:
                result = graph.invoke(Command(resume={"action": "approve"}), config)
            elif sys.stdin.isatty():
                decision = _prompt_recruiter()
                result = graph.invoke(Command(resume=decision), config)
                if _is_interrupted(graph, config, result):
                    _print_review(graph, config)
                    print("Graph paused again after reject/regenerate. Re-run with --thread-id and --resume-action.")
                    print(f"thread_id={thread_id}")
                    print(f"checkpoint={CHECKPOINT_PATH}")
                    return 0
            else:
                print("Graph paused at HITL. Re-run with --thread-id and --resume-action to approve, edit, or reject.")
                print(f"thread_id={thread_id}")
                print(f"checkpoint={CHECKPOINT_PATH}")
                return 0

        if result.get("finalized"):
            print(f"Approved plan written to {result.get('output_path')}")
            print(f"thread_id={thread_id}")
            print(describe_loaded_plan())
            return 0

        print(f"thread_id={thread_id}")
        print(f"checkpoint={CHECKPOINT_PATH}")
        return 0
    finally:
        conn.close()


def _resume_command(args: argparse.Namespace) -> Command:
    if args.resume_action == "edit":
        edits = []
        for item in args.edit:
            if "=" not in item:
                continue
            qid, text = item.split("=", 1)
            edits.append({"id": qid.strip(), "question": text.strip()})
        return Command(resume={"action": "edit", "edits": edits})
    if args.resume_action == "reject":
        return Command(resume={"action": "reject", "reason": args.reason})
    return Command(resume={"action": "approve"})


def _is_interrupted(graph, config, result) -> bool:
    if isinstance(result, dict) and result.get("__interrupt__"):
        return True
    snapshot = graph.get_state(config)
    return bool(snapshot.next)


def _print_review(graph, config) -> None:
    snapshot = graph.get_state(config)
    values = snapshot.values or {}
    questions = values.get("questions") or []
    validation = values.get("validation") or {}
    print("\n================================")
    print("RECRUITER REVIEW")
    print("================================")
    if values.get("sample_mode") or is_sample_github((values.get("github") or {}).get("username") or ""):
        print(SAMPLE_WARNING)
    print(f"Candidate: {(values.get('candidate_profile') or {}).get('name') or 'unknown'}")
    print(f"Role: {(values.get('jd') or {}).get('role') or 'unknown'}")
    print(f"Validation: {'OK' if validation.get('ok') else 'ISSUES'}")
    for issue in validation.get("issues") or []:
        print(f"  - {issue}")
    print()
    for question in questions:
        print(f"{question.get('id')} [{question.get('category')}]")
        print(f"  {question.get('question') or question.get('text')}")
        if question.get("source_reference"):
            print(f"  source: {question.get('source_reference')}")
        print()
    print("Choose: [A] Approve  [E] Edit  [R] Reject")
    print(f"thread_id={values.get('thread_id') or config['configurable']['thread_id']}")
    print(f"checkpoint={CHECKPOINT_PATH}")


def _prompt_recruiter() -> dict:
    choice = input("Enter A, E, or R: ").strip().lower()
    if choice in {"r", "reject"}:
        reason = input("Reject reason (optional): ").strip()
        return {"action": "reject", "reason": reason}
    if choice in {"e", "edit"}:
        edits = []
        while True:
            qid = input("Question id to edit (blank to finish): ").strip()
            if not qid:
                break
            text = input("New question text: ").strip()
            if text:
                edits.append({"id": qid, "question": text})
        return {"action": "edit", "edits": edits}
    return {"action": "approve"}


def _inspect() -> int:
    plan = load_approved_plan()
    if not plan:
        raw = QUESTION_PLAN_PATH
        if raw.is_file():
            plan = json.loads(raw.read_text(encoding="utf-8"))
        else:
            print("No question plan found. Run the prep pipeline first.")
            return 1
    print(describe_loaded_plan())
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
