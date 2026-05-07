from __future__ import annotations

import json

from app.agent.openai_runner import safe_completion_json
from app.agent.prompts import PLANNER_SYSTEM_TEMPLATE
from app.agent.schemas import PerceptionResult, PlannerResult
from app.config import GigConfig, Settings
from app.domain.thread_state import ConversationState


def build_planner_user_block(
    *,
    transcript: str,
    state: ConversationState,
    gig: GigConfig,
    perception: PerceptionResult,
    available_stub_slots: list[str],
    policy_overrides: list[str] | None = None,
) -> str:
    ov = policy_overrides or []
    return f"""
GIG_CONFIGURATION:
{gig.model_dump_json(indent=2)}

AVAILABLE_STUB_SLOTS_ISO (authoritative for stub calendar):
{json.dumps(available_stub_slots, indent=2)}

MEMORY_STATE_JSON:
{state.model_dump_json(indent=2)}

PERCEPTION_JSON:
{perception.model_dump_json(indent=2)}

POLICY_OVERRIDES (must obey over model priors):
{json.dumps(ov, indent=2)}

THREAD_TRANSCRIPT (oldest→newest):
{transcript}
""".strip()


def run_planner(
    *,
    settings: Settings,
    transcript: str,
    state: ConversationState,
    gig: GigConfig,
    perception: PerceptionResult,
    available_stub_slots: list[str],
    policy_overrides: list[str] | None = None,
) -> PlannerResult:
    system = PLANNER_SYSTEM_TEMPLATE.format(tone_key=gig.tone)
    user = build_planner_user_block(
        transcript=transcript,
        state=state,
        gig=gig,
        perception=perception,
        available_stub_slots=available_stub_slots,
        policy_overrides=policy_overrides,
    )
    return safe_completion_json(settings, system=system, user=user, schema_cls=PlannerResult)
