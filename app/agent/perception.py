from __future__ import annotations

from app.agent.anthropic_runner import safe_completion_json
from app.agent.prompts import PERCEPTION_SYSTEM
from app.agent.schemas import PerceptionResult
from app.config import GigConfig, Settings
from app.domain.thread_state import ConversationState


def build_perception_user_block(
    *,
    transcript: str,
    state: ConversationState,
    gig: GigConfig,
) -> str:
    return f"""
GIG_CONFIGURATION:
{gig.model_dump_json(indent=2)}

MEMORY_STATE_JSON:
{state.model_dump_json(indent=2)}

CURRENT_CONVERSATION_PHASE: {state.phase}
(If phase is closed_declined or closed_no_fit, prioritize whether the NEWEST prospect message is re-engaging.)

THREAD_TRANSCRIPT (oldest→newest):
{transcript}
""".strip()


def run_perception(
    *,
    settings: Settings,
    transcript: str,
    state: ConversationState,
    gig: GigConfig,
) -> PerceptionResult:
    user = build_perception_user_block(transcript=transcript, state=state, gig=gig)
    return safe_completion_json(settings, system=PERCEPTION_SYSTEM, user=user, schema_cls=PerceptionResult)
