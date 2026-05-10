"""Deterministic negotiation strategy.

Owns the *numbers and posture* of how the agent moves through a price negotiation:
opening anchor, mid-round counters under the ceiling, and a disciplined walk-away.
Pure functions (no LLM, no I/O) so it can be unit-tested cheaply and so the planner
prompt has crisp guidance to obey instead of inventing offers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.config import GigConfig
from app.domain.enums import ProspectIntent
from app.domain.thread_state import ConversationState

NegotiationPosture = Literal[
    "none",
    "anchor",
    "accept",
    "counter_under_cap",
    "hold_at_cap",
    "walk_away",
]


@dataclass
class NegotiationMove:
    """The recommendation the orchestrator hands to the planner each turn.

    `recommended_offer_usd_hour` is the canonical number the LLM should commit to in
    `negotiation_offer_usd_hour`. The orchestrator clamps any deviation downward to it.
    """

    posture: NegotiationPosture
    recommended_offer_usd_hour: float | None
    should_walk_away: bool
    rationale: str
    next_pushback_rounds: int
    summary_for_planner: str
    debug: dict = field(default_factory=dict)


def _is_money_phase(intent: ProspectIntent) -> bool:
    return intent in {
        ProspectIntent.INTERESTED,
        ProspectIntent.OBJECTING,
        ProspectIntent.SCHEDULING,
        ProspectIntent.CURIOUS,
    }


def compute_negotiation_move(
    *,
    state: ConversationState,
    gig: GigConfig,
    prospect_quotes_usd_hour: list[float],
    intent: ProspectIntent,
) -> NegotiationMove:
    """Decide the next concrete negotiation move.

    Caller is responsible for applying `next_pushback_rounds` back onto state and for
    appending `recommended_offer_usd_hour` to `state.negotiation.offer_history_usd_hour`
    if the planner actually used it.
    """
    ceiling = gig.budget_ceiling_usd_hour
    target = gig.effective_target_usd_hour()
    floor = gig.effective_floor_usd_hour()
    step = gig.effective_concession_step_usd_hour()
    style = gig.negotiation_style
    max_rounds = gig.negotiation_max_rounds
    style_step_mult = {"aggressive": 0.6, "balanced": 1.0, "accommodating": 1.4}.get(style, 1.0)
    effective_step = max(1.0, round(step * style_step_mult, 2))

    last_offer = state.negotiation.last_offer_to_prospect_usd_hour
    rounds = state.negotiation.pushback_rounds_above_ceiling
    latest_quote = prospect_quotes_usd_hour[-1] if prospect_quotes_usd_hour else None

    debug = {
        "ceiling": ceiling,
        "target": target,
        "floor": floor,
        "effective_step": effective_step,
        "style": style,
        "rounds_so_far": rounds,
        "last_offer": last_offer,
        "latest_quote": latest_quote,
        "max_rounds": max_rounds,
    }

    if ceiling is None or target is None:
        return NegotiationMove(
            posture="none",
            recommended_offer_usd_hour=None,
            should_walk_away=False,
            rationale="No budget ceiling configured; let the planner negotiate freely.",
            next_pushback_rounds=rounds,
            summary_for_planner="No deterministic budget guidance — use judgement; do not invent figures.",
            debug=debug,
        )

    if latest_quote is None:
        if last_offer is None and _is_money_phase(intent):
            return NegotiationMove(
                posture="anchor",
                recommended_offer_usd_hour=target,
                should_walk_away=False,
                rationale=f"No quote yet; anchor at target ${target:g}/hr (well under ${ceiling:g} cap).",
                next_pushback_rounds=rounds,
                summary_for_planner=(
                    f"If money comes up, anchor at ${target:g}/hr USD. Hard cap is ${ceiling:g}/hr — "
                    "never exceed it. Otherwise prioritise booking a call."
                ),
                debug=debug,
            )
        return NegotiationMove(
            posture="none",
            recommended_offer_usd_hour=None,
            should_walk_away=False,
            rationale="No prospect quote and not yet a money turn; defer pricing.",
            next_pushback_rounds=rounds,
            summary_for_planner=(
                f"No price discussion yet. If asked, anchor at ${target:g}/hr USD; cap ${ceiling:g}/hr."
            ),
            debug=debug,
        )

    if latest_quote <= ceiling:
        accept_at = max(target, latest_quote)
        accept_at = min(accept_at, ceiling)
        if floor is not None and latest_quote < floor:
            note = (
                f"Quote ${latest_quote:g}/hr is below our floor ${floor:g}; pull up to target "
                f"${target:g}/hr to keep margin."
            )
        else:
            note = f"Quote ${latest_quote:g}/hr fits inside envelope (cap ${ceiling:g}); accept gracefully."
        return NegotiationMove(
            posture="accept",
            recommended_offer_usd_hour=accept_at,
            should_walk_away=False,
            rationale=note,
            next_pushback_rounds=rounds,
            summary_for_planner=(
                f"Prospect at ${latest_quote:g}/hr — under cap. Confirm at ${accept_at:g}/hr USD and "
                "pivot to scheduling. Do not haggle further."
            ),
            debug=debug,
        )

    gap_ratio = latest_quote / ceiling
    very_wide_gap = gap_ratio > 1.5
    rounds_after_this = rounds + 1
    rounds_budget = 1 if very_wide_gap else max_rounds

    if rounds >= rounds_budget:
        return NegotiationMove(
            posture="walk_away",
            recommended_offer_usd_hour=None,
            should_walk_away=True,
            rationale=(
                f"Already pushed back {rounds} time(s); prospect still at ${latest_quote:g}/hr "
                f"vs cap ${ceiling:g}. Time to close graciously."
            ),
            next_pushback_rounds=rounds,
            summary_for_planner=(
                "Walk away on budget. Set internal_action = walk_away_budget. Acknowledge their "
                f"target plainly, name our cap (${ceiling:g}/hr USD), thank them, and close."
            ),
            debug=debug,
        )

    if last_offer is None:
        proposed = target
        posture: NegotiationPosture = "counter_under_cap"
    else:
        proposed = min(last_offer + effective_step, ceiling)
        posture = "hold_at_cap" if proposed >= ceiling - 1e-6 else "counter_under_cap"

    proposed = round(proposed, 2)
    at_cap_note = " (at cap; final number)" if posture == "hold_at_cap" else ""

    if posture == "hold_at_cap":
        summary = (
            f"Final concession: hold firm at the ${ceiling:g}/hr USD cap. State it as our best, "
            "explain envelope briefly, invite them to align, but flag this is the ceiling — next "
            "refusal closes the thread."
        )
    else:
        summary = (
            f"Counter at ${proposed:g}/hr USD{at_cap_note}. Acknowledge their ${latest_quote:g}/hr, "
            "explain the envelope, propose this number, and invite alignment toward booking a call. "
            f"Hard cap is ${ceiling:g}/hr — never exceed it in text or in negotiation_offer_usd_hour."
        )

    return NegotiationMove(
        posture=posture,
        recommended_offer_usd_hour=proposed,
        should_walk_away=False,
        rationale=(
            f"Counter ${proposed:g} (prev offer {last_offer}, step {effective_step}, cap {ceiling}, "
            f"round {rounds_after_this}/{rounds_budget})."
        ),
        next_pushback_rounds=rounds_after_this,
        summary_for_planner=summary,
        debug=debug,
    )
