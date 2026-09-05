"""Shared LiveKit join-token minting used by token_server and (later) FastAPI."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from livekit import api

from config import AGENT_NAME, load_settings

SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]+")


@dataclass(frozen=True)
class LiveKitJoinToken:
    token: str
    url: str
    room: str
    identity: str


def safe_identity(name: str) -> str:
    cleaned = SAFE_NAME.sub("-", name.strip())[:40].strip("-")
    return cleaned or "candidate"


class LiveKitTokenService:
    """Single implementation for minting candidate join tokens + agent dispatch."""

    def mint_join_token(
        self,
        name: str,
        *,
        room: str | None = None,
        identity: str | None = None,
        agent_name: str | None = None,
    ) -> LiveKitJoinToken:
        settings = load_settings()
        resolved_identity = identity or f"{safe_identity(name)}-{uuid.uuid4().hex[:6]}"
        resolved_room = room or f"firstround-{resolved_identity}"
        resolved_agent = agent_name or settings.agent_name or AGENT_NAME
        token = (
            api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(resolved_identity)
            .with_name(name)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=resolved_room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .with_room_config(
                api.RoomConfiguration(
                    agents=[
                        api.RoomAgentDispatch(agent_name=resolved_agent),
                    ],
                ),
            )
            .to_jwt()
        )
        return LiveKitJoinToken(
            token=token,
            url=settings.livekit_url,
            room=resolved_room,
            identity=resolved_identity,
        )


_default_service: LiveKitTokenService | None = None


def get_livekit_token_service() -> LiveKitTokenService:
    global _default_service
    if _default_service is None:
        _default_service = LiveKitTokenService()
    return _default_service
