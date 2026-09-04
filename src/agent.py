"""Phase 1 LiveKit + Gemini Live interviewer. Vendor avatars stay disabled."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from google.genai import types
from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AgentStateChangedEvent,
    ConversationItemAddedEvent,
    JobContext,
    UserStateChangedEvent,
    room_io,
)
from livekit.agents.llm import ChatMessage
from livekit.plugins import google

from config import AGENT_NAME, GEMINI_LIVE_MODEL, ROOT_DIR, load_settings
from plan_loader import (
    compact_briefing,
    follow_up_instructions,
    is_ready_for_live_interview,
    load_approved_plan,
    opening_instructions,
    turn_instructions,
    wrap_up_instructions,
)
from realtime.controller import InterviewController
from realtime.store import default_store, interview_status_for

TRANSCRIPT_PATH = ROOT_DIR / "output" / "interview_transcript.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("firstround.agent")

def _live_interviewer_prompt() -> str:
    path = ROOT_DIR / "prompts" / "live_interviewer.md"
    return path.read_text(encoding="utf-8").strip()


INTERVIEWER_INSTRUCTIONS = _live_interviewer_prompt()


def _interview_ui_payload(controller: InterviewController) -> dict:
    total = len(controller.questions)
    wrap = controller.phase == "wrap_up" or controller._wrap_up_emitted
    index = int(getattr(controller, "index", 0) or 0) + 1
    if wrap:
        index = min(max(index, 1), total or 1)
    phase = "wrap_up" if wrap else ("follow_up" if controller.follow_up_count else "question")
    return {
        "type": "interview_ui",
        "phase": phase,
        "question_id": controller.current_question_id() or controller.last_answered_id,
        "question_index": index,
        "questions_total": total,
        "completed": wrap,
    }


async def _publish_interview_ui(session: AgentSession, controller: InterviewController) -> None:
    try:
        room = getattr(session, "room", None)
        participant = getattr(room, "local_participant", None) if room else None
        if participant is None:
            return
        payload = json.dumps(_interview_ui_payload(controller)).encode("utf-8")
        await participant.publish_data(payload, reliable=True)
    except Exception:
        logger.exception("[UI] failed to publish interview state")


def _persist_transcript(controller: InterviewController) -> None:
    turns = controller.get_transcript()
    TRANSCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_PATH.write_text(
        json.dumps(turns, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("[TRANSCRIPT] saved turns=%s path=%s", len(turns), TRANSCRIPT_PATH)


def _interview_id(ctx: JobContext) -> str:
    job_id = str(getattr(getattr(ctx, "job", None), "id", "") or "").strip()
    room = str(getattr(ctx.room, "name", "") or "").strip()
    return job_id or room or f"interview-{uuid.uuid4().hex[:12]}"


class Interviewer(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=INTERVIEWER_INSTRUCTIONS)


def _candidate_name(ctx: JobContext) -> str:
    for participant in ctx.room.remote_participants.values():
        name = (participant.name or "").strip()
        if name:
            return name
        identity = (participant.identity or "").strip()
        if identity and not identity.startswith("agent"):
            return identity
    return "there"


def _attach_turn_logging(session: AgentSession) -> None:
    state = {
        "agent_speaking": False,
        "candidate_speaking": False,
        "candidate_stopped_at": None,
    }

    @session.on("agent_state_changed")
    def on_agent_state(ev: AgentStateChangedEvent) -> None:
        if ev.new_state == "speaking":
            state["agent_speaking"] = True
            logger.info("[TURN] Agent speaking")
            stopped_at = state["candidate_stopped_at"]
            if stopped_at is not None:
                latency_ms = int((time.monotonic() - stopped_at) * 1000)
                logger.info("[LATENCY] candidate_stop_to_agent_audio_ms=%s", latency_ms)
                state["candidate_stopped_at"] = None
        elif ev.old_state == "speaking":
            state["agent_speaking"] = False
            if ev.new_state == "listening":
                logger.info("[TURN] Listening to candidate")
            elif ev.new_state == "thinking":
                logger.info("[TURN] Agent thinking")
        elif ev.new_state == "listening":
            logger.info("[TURN] Listening to candidate")
        elif ev.new_state == "thinking":
            logger.info("[TURN] Agent thinking")

    @session.on("user_state_changed")
    def on_user_state(ev: UserStateChangedEvent) -> None:
        if ev.new_state == "speaking":
            state["candidate_speaking"] = True
            logger.info("[TURN] Candidate started speaking")
            if state["agent_speaking"]:
                logger.info("[INTERRUPT] Agent interrupted")
        elif ev.old_state == "speaking":
            state["candidate_speaking"] = False
            state["candidate_stopped_at"] = time.monotonic()
            logger.info("[TURN] Candidate stopped speaking")

    @session.on("conversation_item_added")
    def on_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, ChatMessage):
            return
        if item.role == "assistant" and getattr(item, "interrupted", False):
            logger.info("[INTERRUPT] Agent speech item marked interrupted")


def _attach_linear_flow(
    session: AgentSession,
    controller: InterviewController,
    plan: dict,
    spoken_name: str,
) -> None:
    seen_user_items: set[str] = set()
    tasks: set[asyncio.Task] = set()

    @session.on("user_state_changed")
    def on_candidate_speech(ev: UserStateChangedEvent) -> None:
        if ev.new_state == "speaking":
            controller.mark_candidate_speaking()
        elif ev.old_state == "speaking":
            controller.mark_candidate_stopped()

    @session.on("conversation_item_added")
    def on_candidate_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, ChatMessage) or item.role != "user":
            return
        item_id = str(getattr(item, "id", "") or "")
        if item_id and item_id in seen_user_items:
            return
        text = (item.text_content or "").strip()
        if not text:
            return
        action = controller.try_complete_answer(text, event_id=item_id)
        if action == "ignore":
            return
        if item_id:
            seen_user_items.add(item_id)
        answered = controller.last_answered_id or "question"
        logger.info("[PLAN] completed %s", answered)
        if controller.last_eval:
            logger.info("[EVAL] %s=%s", answered, controller.last_eval)
        logger.info("[TIMER] interview elapsed=%s", int(controller.interview_duration))
        task = asyncio.create_task(_continue_after_answer(action, answered))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def _continue_after_answer(action: str, answered: str) -> None:
        try:
            if action == "wrap_up":
                if controller.time_limit_reached():
                    logger.info("[TIMER] time limit reached")
                logger.info("[PLAN] wrap_up")
                controller.record_interviewer_turn(
                    "Thank you for your time today. That concludes the interview.",
                    "closing",
                )
                logger.info("[TRANSCRIPT] turns=%s", len(controller.get_transcript()))
                _persist_transcript(controller)
                await _publish_interview_ui(session, controller)
                await session.generate_reply(
                    instructions=wrap_up_instructions(spoken_name)
                )
                return
            if action == "follow_up":
                briefing = compact_briefing(plan, answered)
                logger.info(
                    "[PLAN] follow_up %s count=%s",
                    answered,
                    controller.follow_up_count,
                )
                probe = ""
                triggers = briefing.get("follow_up_triggers") or []
                if isinstance(triggers, list) and triggers:
                    probe = str(triggers[min(controller.follow_up_count - 1, len(triggers) - 1)])
                controller.record_interviewer_turn(
                    probe or "Follow-up on the current question.",
                    "follow_up",
                )
                controller.note_question_asked()
                await _publish_interview_ui(session, controller)
                await session.generate_reply(
                    instructions=follow_up_instructions(
                        briefing,
                        str(controller.last_eval or "shallow"),
                        controller.follow_up_count,
                    )
                )
                return
            qid = controller.current_question_id()
            briefing = compact_briefing(plan, qid)
            logger.info("[PLAN] asking %s", briefing.get("question_id") or qid)
            controller.record_interviewer_turn(
                str(briefing.get("question") or ""),
                "question",
            )
            controller.note_question_asked()
            await _publish_interview_ui(session, controller)
            await session.generate_reply(instructions=turn_instructions(briefing))
        except Exception:
            logger.exception("[PLAN] failed to continue after candidate answer")

    async def _watch_timer() -> None:
        try:
            while controller.phase != "wrap_up":
                await asyncio.sleep(2)
                if controller.should_wrap_up_now() and controller.begin_wrap_up():
                    logger.info(
                        "[TIMER] interview elapsed=%s",
                        int(controller.interview_duration),
                    )
                    logger.info("[TIMER] time limit reached")
                    logger.info("[PLAN] wrap_up")
                    controller.record_interviewer_turn(
                        "Thank you for your time today. That concludes the interview.",
                        "closing",
                    )
                    logger.info("[TRANSCRIPT] turns=%s", len(controller.get_transcript()))
                    _persist_transcript(controller)
                    await _publish_interview_ui(session, controller)
                    await session.generate_reply(
                        instructions=wrap_up_instructions(spoken_name)
                    )
                    return
        except Exception:
            logger.exception("[TIMER] watch failed")

    tasks.add(asyncio.create_task(_watch_timer()))


def _realtime_model() -> google.realtime.RealtimeModel:
    return google.realtime.RealtimeModel(
        model=GEMINI_LIVE_MODEL,
        voice="Puck",
        temperature=0.7,
        instructions=INTERVIEWER_INSTRUCTIONS,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        thinking_config=types.ThinkingConfig(include_thoughts=False),
        context_window_compression=types.ContextWindowCompressionConfig(
            trigger_tokens=25600,
            sliding_window=types.SlidingWindow(target_tokens=12000),
        ),
        session_resumption=types.SessionResumptionConfig(),
    )


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def interview_session(ctx: JobContext) -> None:
    settings = load_settings()
    logger.info(
        "[BOOT] mode=%s model=%s agent=%s",
        settings.mode,
        settings.gemini_model,
        settings.agent_name,
    )
    logger.info("[BOOT] Vendor avatar disabled (local 2D face only)")

    plan = load_approved_plan()
    if not is_ready_for_live_interview(plan):
        logger.error("[PLAN] No approved interview plan — refusing interview")
        return

    questions = plan.get("questions") or []
    candidate_name = str((plan.get("candidate") or {}).get("name") or "").strip()
    logger.info("[PLAN] approved interview plan loaded")
    logger.info("[PLAN] questions=%s", len(questions))
    if candidate_name:
        logger.info("[PLAN] candidate=%s", candidate_name)

    try:
        store = default_store()
        logger.info("[INTERVIEW] store_path=%s", store.path)
        interview_id = _interview_id(ctx)
        job = plan.get("job") or {}
        role = str(job.get("role") or "").strip()
        company = str(job.get("company") or "").strip()
        store.create_interview(
            interview_id, candidate=candidate_name, role=role, company=company
        )
        if not store.path.is_file():
            raise RuntimeError(f"SQLite file was not created: {store.path}")
        logger.info("[INTERVIEW] created interview_id=%s", interview_id)
    except Exception:
        logger.exception("[INTERVIEW] sqlite store failed to initialize")
        raise

    def _persist_live(current: InterviewController, status: str | None = None) -> None:
        try:
            store.save_from_controller(
                interview_id,
                current,
                status=status,
                candidate=candidate_name,
                role=role,
                company=company,
            )
            if not store.path.is_file():
                raise RuntimeError(f"SQLite file missing after persist: {store.path}")
        except Exception:
            logger.exception(
                "[INTERVIEW] persist failed interview_id=%s path=%s",
                interview_id,
                store.path,
            )

    controller = InterviewController(plan, persist=_persist_live)

    async def _save_on_shutdown() -> None:
        disconnected = controller.phase != "wrap_up" and not controller._wrap_up_emitted
        status = interview_status_for(controller, disconnected=disconnected)
        _persist_live(controller, status=status)
        _persist_transcript(controller)
        logger.info("[INTERVIEW] disconnected")
        logger.info("[INTERVIEW] persisted interview_id=%s", interview_id)
        logger.info("[INTERVIEW] status=%s", status)
        logger.info("[INTERVIEW] store_path=%s", store.path)

    ctx.add_shutdown_callback(_save_on_shutdown)
    briefing = compact_briefing(plan, controller.current_question_id())

    session = AgentSession(llm=_realtime_model())
    _attach_turn_logging(session)

    await session.start(
        room=ctx.room,
        agent=Interviewer(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
            text_output=False,
        ),
    )

    participant = await ctx.wait_for_participant()
    name = (
        (participant.name or "").strip()
        or candidate_name
        or _candidate_name(ctx)
    )
    _attach_linear_flow(session, controller, plan, name)
    controller.start_interview()
    logger.info("[BOOT] Candidate joined identity=%s", participant.identity)
    logger.info("[TIMER] interview elapsed=0")
    logger.info("[PLAN] asking %s", briefing.get("question_id") or "q1")

    controller.record_interviewer_turn(str(briefing.get("question") or ""), "question")
    controller.note_question_asked()
    await _publish_interview_ui(session, controller)
    await session.generate_reply(instructions=opening_instructions(briefing, name))


if __name__ == "__main__":
    load_settings()
    agents.cli.run_app(server)
