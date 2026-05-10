from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.domain.enums import ConversationPhase


class BookingRecord(BaseModel):
    slot_iso: str
    status: str = Field(description="'proposed', 'confirmed', 'cancelled'")
    marked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


class NegotiationFacts(BaseModel):
    """Ground truth the agent must not contradict."""

    ceiling_usd_hour: float | None = None
    last_offer_to_prospect_usd_hour: float | None = None
    last_quote_from_prospect_usd_hour: float | None = None
    objections_noted: list[str] = Field(default_factory=list)
    pushback_rounds_above_ceiling: int = Field(
        default=0,
        description="How many turns the prospect has stayed above ceiling after we already engaged on price.",
    )
    offer_history_usd_hour: list[float] = Field(
        default_factory=list,
        description="Chronological list of numeric offers we've made to the prospect.",
    )


class ConversationState(BaseModel):
    phase: ConversationPhase = ConversationPhase.INITIATED
    booking_history: list[BookingRecord] = Field(default_factory=list)
    negotiation: NegotiationFacts = Field(default_factory=NegotiationFacts)
    reschedule_count: int = 0
    last_prospect_extracted_rates: list[float] = Field(default_factory=list)
    awaiting_slot_choice: bool = False


def serialize_state(state: ConversationState) -> dict:
    return state.model_dump(mode="json")


def parse_state(blob: dict | None) -> ConversationState:
    if not blob:
        return ConversationState()
    # Upgrade path: pydantic ignores unknown keys in strict could fail — use model_validate loose
    return ConversationState.model_validate(blob)
