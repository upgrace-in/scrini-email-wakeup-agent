from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agent.outreach import OutreachEmail, compose_outreach
from app.agent.perception import run_perception
from app.agent.planner import run_planner
from app.agent.schemas import PerceptionResult, PlannerResult
from app.calendar.stub import StubCalendar
from app.config import GigConfig, Settings
from app.domain.enums import ConversationPhase, MessageDirection, ProspectIntent
from app.domain.thread_state import BookingRecord, ConversationState, NegotiationFacts
from app.email.send import SentEmailReceipt, send_outbound
from app.storage.models import Conversation
from app.storage.repository import ConversationRepository, transcript_for_prompt

log = logging.getLogger(__name__)

CLOSED = (
    ConversationPhase.CLOSED_DECLINED,
    ConversationPhase.CLOSED_NO_FIT,
    ConversationPhase.CLOSED_SUCCESS,
)


def derive_phase_after_turn(state: ConversationState) -> ConversationPhase:
    """Single place for coarse phase derivation after persisted effects."""

    if state.phase in CLOSED:
        return state.phase
    if any(b.status == "confirmed" for b in state.booking_history):
        return ConversationPhase.BOOKED
    if state.phase == ConversationPhase.AWAITING_REPLY:
        return ConversationPhase.NEGOTIATING
    return state.phase


@dataclass
class AgentRunReceipt:
    conversation_id: str
    outbound_sent: SentEmailReceipt | None
    phase_after: ConversationPhase
    planner: PlannerResult | None
    perception: PerceptionResult | None


class EmailAgentOrchestrator:
    """Perception → guardrail overlays → planner → side effects."""

    def __init__(self, *, settings: Settings, repo: ConversationRepository, calendar: StubCalendar):
        self._settings = settings
        self._repo = repo
        self._calendar = calendar

    def initiate_outreach(
        self,
        *,
        prospect_email: str,
        preset_key: str | None = None,
        idempotency_key: str | None = None,
        subject_hint: str | None = None,
    ) -> tuple[Conversation, SentEmailReceipt, OutreachEmail]:
        if idempotency_key:
            existing = self._repo.find_by_idempotency(idempotency_key)
            if existing is not None:
                bundle_existing = self._repo.get_with_messages(existing.id)
                msgs = bundle_existing.messages if bundle_existing else []
                last_out = next(
                    (m for m in reversed(msgs) if m.direction == MessageDirection.OUTBOUND.value),
                    None,
                )
                log.info("outreach idempotent hit conversation_id=%s", existing.id)
                rec = SentEmailReceipt(
                    provider_message_id=last_out.provider_message_id if last_out else None,
                    mock=True,
                )
                body = last_out.body_text if last_out else ""
                subj = (last_out.subject if last_out and last_out.subject else None) or subject_hint
                fallback_title = ""
                gt = existing.gig_snapshot_json.get("gig_title")
                if isinstance(gt, str):
                    fallback_title = gt
                subject_final = (subj or fallback_title or existing.preset_key)[:120]
                return existing, rec, OutreachEmail(subject=subject_final, body=body)

        preset = preset_key or self._settings.default_agent_preset
        gig = self._settings.preset_gig_config(preset)
        state = ConversationState(
            phase=ConversationPhase.INITIATED,
            negotiation=NegotiationFacts(ceiling_usd_hour=gig.budget_ceiling_usd_hour),
        )
        outreach = compose_outreach(settings=self._settings, gig=gig, prospect_email=prospect_email)
        subject_base = subject_hint or outreach.subject
        conv = self._repo.create_outreach_thread(
            prospect_email=prospect_email,
            subject=subject_base,
            preset_key=preset,
            gig_snapshot=gig.model_dump(mode="json"),
            state=state,
            idempotency_key=idempotency_key,
        )
        receipt = send_outbound(
            settings=self._settings,
            to_email=prospect_email,
            subject=subject_base,
            body=outreach.body,
        )
        self._repo.append_message(
            conversation_id=conv.id,
            direction=MessageDirection.OUTBOUND,
            body_text=outreach.body,
            subject=subject_base,
            provider_message_id=receipt.provider_message_id,
            in_reply_to_provider_id=None,
            metadata={"kind": "outreach"},
        )
        state.phase = ConversationPhase.AWAITING_REPLY
        self._repo.save_state(conv, state)
        log.info("outreach_sent conversation_id=%s to=%s", conv.id, prospect_email)
        return conv, receipt, outreach

    def process_conversation(self, conversation_id: str) -> AgentRunReceipt:
        bundle = self._repo.get_with_messages(conversation_id)
        if bundle is None:
            raise ValueError("conversation not found")
        conv, messages = bundle.conversation, bundle.messages
        gig = GigConfig.model_validate(conv.gig_snapshot_json)
        state = self._repo.load_state(conv)

        if state.phase in CLOSED:
            log.info("skip_closed conversation_id=%s phase=%s", conversation_id, state.phase)
            return AgentRunReceipt(
                conversation_id=conversation_id,
                outbound_sent=None,
                phase_after=state.phase,
                planner=None,
                perception=None,
            )

        transcript = transcript_for_prompt(messages)
        perception = run_perception(settings=self._settings, transcript=transcript, state=state, gig=gig)

        if perception.quoted_rates_usd_hour:
            state.last_prospect_extracted_rates = sorted(set(perception.quoted_rates_usd_hour))
            state.negotiation.last_quote_from_prospect_usd_hour = (
                state.last_prospect_extracted_rates[-1] if state.last_prospect_extracted_rates else None
            )

        policy_overrides: list[str] = []
        if perception.is_hard_decline or perception.intent == ProspectIntent.DECLINING:
            policy_overrides.append(
                "Prospect is declining or explicitly not interested. Close graciously without pressure."
            )
        if perception.is_cancellation_of_scheduled_call:
            policy_overrides.append(
                "Prospect cancelled or must reschedule a concrete call. Acknowledge graciously, summarize "
                "continuity, propose fresh concrete times from AVAILABLE_STUB_SLOTS_ISO."
            )
            apply_cancellation_to_state(state)

        if budget_impossible(gig, perception.quoted_rates_usd_hour):
            policy_overrides.append(
                "Their stated hourly expectations are firmly above ceiling with zero overlap — walk away politely."
            )

        planner: PlannerResult | None = None

        if perception.is_hard_decline or perception.intent == ProspectIntent.DECLINING:
            planner = PlannerResult(
                reply_plaintext=(
                    "Thanks for the straight answer — appreciate it. Totally understand prioritizing what's already "
                    "on your plate. If your situation changes later, you're welcome to reach out. Pulling cheer for "
                    "what you're building."
                ),
                internal_action="acknowledge_decline",
                planner_notes="hard_decline_short_circuit",
            )
            state.phase = ConversationPhase.CLOSED_DECLINED
        elif budget_impossible(gig, perception.quoted_rates_usd_hour):
            planner = PlannerResult(
                reply_plaintext=(
                    "Appreciate you sharing rate expectations plainly. Our approved envelope for this role tops out "
                    f"below ${min(perception.quoted_rates_usd_hour):g}/hr you're targeting, so we won't waste your "
                    "time negotiating into a mismatch. Thank you anyway — rooting for what's next on your side."
                ),
                internal_action="walk_away_budget",
                planner_notes="deterministic_budget_walkaway",
            )
            state.phase = ConversationPhase.CLOSED_NO_FIT
        else:
            slots = list(self._settings.stub_slot_list())
            planner = run_planner(
                settings=self._settings,
                transcript=transcript,
                state=state,
                gig=gig,
                perception=perception,
                available_stub_slots=slots,
                policy_overrides=policy_overrides or None,
            )
            self._apply_booking_stub(state=state, planner=planner, conversation_id=str(conv.id))

        assert planner is not None

        reply_subject = conv.subject if conv.subject.lower().startswith("re:") else f"Re: {conv.subject}"
        outbound = send_outbound(
            settings=self._settings,
            to_email=conv.prospect_email,
            subject=reply_subject.strip(),
            body=planner.reply_plaintext.strip(),
        )
        inbound_last_provider_id = messages[-1].provider_message_id if messages else None
        self._repo.append_message(
            conversation_id=conv.id,
            direction=MessageDirection.OUTBOUND,
            body_text=planner.reply_plaintext.strip(),
            subject=reply_subject.strip(),
            provider_message_id=outbound.provider_message_id,
            in_reply_to_provider_id=inbound_last_provider_id,
            metadata={
                "internal_action": planner.internal_action,
                "perception_intent": perception.intent.value,
            },
        )

        if state.phase not in CLOSED:
            state.phase = derive_phase_after_turn(state)

        self._repo.save_state(conv, state)
        log.info(
            "agent_turn conversation=%s perception=%s action=%s phase=%s",
            conv.id,
            perception.intent,
            planner.internal_action,
            state.phase,
        )
        return AgentRunReceipt(
            conversation_id=conv.id,
            outbound_sent=outbound,
            phase_after=state.phase,
            planner=planner,
            perception=perception,
        )

    def _apply_booking_stub(self, *, state: ConversationState, planner: PlannerResult, conversation_id: str) -> None:
        slot = (planner.slot_iso_to_book or "").strip()
        if planner.internal_action != "confirm_booking" or not slot:
            return
        if slot not in set(s.strip() for s in self._settings.stub_slot_list()):
            log.warning("planner.slot_rejected_stub_mismatch conversation=%s slot=%s", conversation_id, slot)
            return
        history = list(state.booking_history)
        history.append(BookingRecord(slot_iso=slot, status="confirmed"))
        state.booking_history = history
        state.awaiting_slot_choice = False
        self._calendar.log_stub_book(slot)


def budget_impossible(gig: GigConfig, rates: list[float]) -> bool:
    ceiling = gig.budget_ceiling_usd_hour
    if ceiling is None or not rates:
        return False
    return min(rates) > ceiling


def apply_cancellation_to_state(state: ConversationState) -> None:
    hist = list(state.booking_history)
    mutated = False
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].status in {"confirmed", "proposed"}:
            hist[i] = hist[i].model_copy(update={"status": "cancelled"})
            mutated = True
            break
    state.booking_history = hist
    if not mutated:
        # Still reschedule intent — keep phase fluid without inflating counters spuriously.
        state.phase = ConversationPhase.RESCHEDULE_OFFERED
        return
    state.reschedule_count += 1
    state.phase = ConversationPhase.RESCHEDULE_OFFERED
