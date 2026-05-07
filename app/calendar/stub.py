from __future__ import annotations

import logging

from app.domain.thread_state import BookingRecord, ConversationState
from app.config import Settings

log = logging.getLogger(__name__)


class StubCalendar:
    """STUB: Replace with Google Calendar API or Cal.com webhooks."""

    def __init__(self, slots_iso: list[str]):
        self._slots = tuple(slots_iso)

    def available_slots_offer_text(self, state: ConversationState) -> str:
        occupied = self._currently_held_slots(state)
        avail = [s for s in self._slots if s not in occupied]
        if not avail:
            avail = list(self._slots)
        bullets = ", ".join(avail)
        return bullets

    def _currently_held_slots(self, state: ConversationState) -> set[str]:
        held = {b.slot_iso for b in state.booking_history if b.status in {"confirmed", "proposed"}}
        return held

    def normalize_booking_candidate(self, slot_iso: str) -> bool:
        slug = slot_iso.strip()
        return slug in set(self._slots)

    def log_stub_book(self, slot_iso: str) -> dict:
        log.info("STUB calendar hold committed slot=%s", slot_iso)
        return {"stub": True, "slot_iso": slot_iso, "calendar_mode": "stub"}
