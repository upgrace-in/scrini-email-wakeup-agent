from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import ProspectIntent


class PerceptionResult(BaseModel):
    intent: ProspectIntent = Field(description="Highest-signal classification of latest prospect message.")
    is_cancellation_of_scheduled_call: bool = Field(
        default=False,
        description=(
            "True if they are backing out of a previously agreed/proposed concrete call time "
            "(not merely asking to schedule)."
        ),
    )
    is_hard_decline: bool = Field(default=False)
    quoted_rates_usd_hour: list[float] = Field(
        default_factory=list,
        description="Numeric hourly USD asks from prospect, if explicit.",
    )
    proposed_datetimes_iso: list[str] = Field(
        default_factory=list,
        description="Concrete slot proposals extracted from prose, RFC3339 if possible.",
    )
    objections: list[str] = Field(default_factory=list)
    ambiguity_note: str | None = Field(
        default=None,
        description="If intent is ambiguous, state what clarification is missing.",
    )
    rationale: str = Field(description="1-3 sentences referencing thread evidence")


class PlannerResult(BaseModel):
    reply_plaintext: str = Field(description="Complete email body, no markdown code fences.")
    internal_action: str = Field(
        description=(
            "One of: reply_only | propose_times | confirm_booking | reschedule_offer | "
            "walk_away_budget | acknowledge_decline"
        ),
    )
    negotiation_offer_usd_hour: float | None = Field(
        default=None,
        description="If making or countering a numeric rate within budget ceiling.",
    )
    slot_iso_to_book: str | None = Field(
        default=None,
        description="If confirming a booking, must match stub calendar slot or prospect proposal.",
    )
    planner_notes: str = Field(default="", description="Short rationale for operators/logging.")
