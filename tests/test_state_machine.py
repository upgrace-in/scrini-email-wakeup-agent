from __future__ import annotations

from app.agent.orchestrator import apply_cancellation_to_state, budget_impossible, derive_phase_after_turn
from app.config import GigConfig
from app.domain.enums import ConversationPhase
from app.domain.thread_state import BookingRecord, ConversationState


def sample_gig(ceiling: float | None = 120.0) -> GigConfig:
    return GigConfig(
        gig_title="Title",
        gig_summary="Summary",
        role_focus=["backend"],
        budget_ceiling_usd_hour=ceiling,
    )


def test_budget_impossible_below_ceiling_returns_false():
    gig = sample_gig(120)
    assert budget_impossible(gig, [80, 100]) is False


def test_budget_impossible_above_returns_true():
    gig = sample_gig(120)
    assert budget_impossible(gig, [150]) is True


def test_budget_none_never_impossible_even_with_rates():
    gig = sample_gig(None)
    assert budget_impossible(gig, [999]) is False


def test_apply_cancellation_marks_most_recent_booking_cancelled_only():
    state = ConversationState(
        booking_history=[
            BookingRecord(slot_iso="a", status="confirmed"),
            BookingRecord(slot_iso="b", status="confirmed"),
        ],
        reschedule_count=0,
    )
    apply_cancellation_to_state(state)
    statuses = [b.status for b in state.booking_history]
    assert statuses == ["confirmed", "cancelled"]
    assert state.reschedule_count == 1
    assert state.phase == ConversationPhase.RESCHEDULE_OFFERED


def test_derive_prefers_explicit_closed():
    state = ConversationState(phase=ConversationPhase.CLOSED_NO_FIT)
    assert derive_phase_after_turn(state) == ConversationPhase.CLOSED_NO_FIT


def test_derive_books_into_booked_when_confirmed_exists():
    state = ConversationState(
        phase=ConversationPhase.NEGOTIATING,
        booking_history=[BookingRecord(slot_iso="slot", status="confirmed")],
    )
    assert derive_phase_after_turn(state) == ConversationPhase.BOOKED


def test_apply_cancellation_without_active_booking_does_not_increment_counter():
    state = ConversationState(booking_history=[], reschedule_count=0)
    apply_cancellation_to_state(state)
    assert state.booking_history == []
    assert state.reschedule_count == 0
    assert state.phase == ConversationPhase.RESCHEDULE_OFFERED
