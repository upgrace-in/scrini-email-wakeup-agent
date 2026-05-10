from __future__ import annotations

from app.agent.negotiation import compute_negotiation_move
from app.config import GigConfig
from app.domain.enums import ProspectIntent
from app.domain.thread_state import ConversationState, NegotiationFacts


def gig(
    *,
    ceiling: float | None = 120.0,
    target: float | None = 95.0,
    floor: float | None = 80.0,
    step: float | None = 10.0,
    max_rounds: int = 3,
    style: str = "balanced",
) -> GigConfig:
    return GigConfig(
        gig_title="t",
        gig_summary="s",
        role_focus=["x"],
        budget_ceiling_usd_hour=ceiling,
        budget_target_usd_hour=target,
        budget_floor_usd_hour=floor,
        concession_step_usd_hour=step,
        negotiation_max_rounds=max_rounds,
        negotiation_style=style,  # type: ignore[arg-type]
    )


def state_with(*, last_offer: float | None = None, rounds: int = 0) -> ConversationState:
    return ConversationState(
        negotiation=NegotiationFacts(
            ceiling_usd_hour=120.0,
            last_offer_to_prospect_usd_hour=last_offer,
            pushback_rounds_above_ceiling=rounds,
        )
    )


def test_no_ceiling_returns_none_posture():
    move = compute_negotiation_move(
        state=state_with(),
        gig=gig(ceiling=None, target=None),
        prospect_quotes_usd_hour=[150.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "none"
    assert move.recommended_offer_usd_hour is None
    assert move.should_walk_away is False


def test_anchor_when_money_phase_and_no_quote():
    move = compute_negotiation_move(
        state=state_with(),
        gig=gig(),
        prospect_quotes_usd_hour=[],
        intent=ProspectIntent.INTERESTED,
    )
    assert move.posture == "anchor"
    assert move.recommended_offer_usd_hour == 95.0


def test_no_anchor_for_pure_scheduling_with_no_quote_and_no_money_intent():
    move = compute_negotiation_move(
        state=state_with(),
        gig=gig(),
        prospect_quotes_usd_hour=[],
        intent=ProspectIntent.RESCHEDULING_REQUEST,
    )
    assert move.posture == "none"
    assert move.recommended_offer_usd_hour is None


def test_accept_when_quote_under_ceiling_pulls_up_to_target():
    move = compute_negotiation_move(
        state=state_with(),
        gig=gig(),
        prospect_quotes_usd_hour=[60.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "accept"
    assert move.recommended_offer_usd_hour == 95.0
    assert move.should_walk_away is False


def test_accept_at_quote_when_quote_above_target_under_ceiling():
    move = compute_negotiation_move(
        state=state_with(),
        gig=gig(),
        prospect_quotes_usd_hour=[110.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "accept"
    assert move.recommended_offer_usd_hour == 110.0


def test_first_counter_anchors_at_target_when_above_cap():
    move = compute_negotiation_move(
        state=state_with(),
        gig=gig(),
        prospect_quotes_usd_hour=[150.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "counter_under_cap"
    assert move.recommended_offer_usd_hour == 95.0
    assert move.next_pushback_rounds == 1


def test_subsequent_counter_steps_up_by_concession_step():
    move = compute_negotiation_move(
        state=state_with(last_offer=95.0, rounds=1),
        gig=gig(),
        prospect_quotes_usd_hour=[140.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "counter_under_cap"
    assert move.recommended_offer_usd_hour == 105.0
    assert move.next_pushback_rounds == 2


def test_counter_clamps_to_ceiling_and_marks_hold_at_cap():
    move = compute_negotiation_move(
        state=state_with(last_offer=115.0, rounds=2),
        gig=gig(step=20.0),
        prospect_quotes_usd_hour=[140.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "hold_at_cap"
    assert move.recommended_offer_usd_hour == 120.0


def test_walk_away_after_max_rounds_exceeded():
    move = compute_negotiation_move(
        state=state_with(last_offer=120.0, rounds=3),
        gig=gig(max_rounds=3),
        prospect_quotes_usd_hour=[140.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "walk_away"
    assert move.should_walk_away is True
    assert move.recommended_offer_usd_hour is None


def test_very_wide_gap_walks_away_after_one_pushback():
    move = compute_negotiation_move(
        state=state_with(last_offer=95.0, rounds=1),
        gig=gig(),
        prospect_quotes_usd_hour=[300.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert move.posture == "walk_away"
    assert move.should_walk_away is True


def test_aggressive_style_takes_smaller_concession_steps():
    base = compute_negotiation_move(
        state=state_with(last_offer=95.0, rounds=1),
        gig=gig(step=10.0, style="balanced"),
        prospect_quotes_usd_hour=[140.0],
        intent=ProspectIntent.OBJECTING,
    )
    aggressive = compute_negotiation_move(
        state=state_with(last_offer=95.0, rounds=1),
        gig=gig(step=10.0, style="aggressive"),
        prospect_quotes_usd_hour=[140.0],
        intent=ProspectIntent.OBJECTING,
    )
    assert base.recommended_offer_usd_hour is not None
    assert aggressive.recommended_offer_usd_hour is not None
    assert aggressive.recommended_offer_usd_hour < base.recommended_offer_usd_hour
