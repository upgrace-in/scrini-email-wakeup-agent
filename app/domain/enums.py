from __future__ import annotations

from enum import StrEnum


class MessageDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class ConversationPhase(StrEnum):
    INITIATED = "initiated"
    AWAITING_REPLY = "awaiting_reply"
    NEGOTIATING = "negotiating"
    SCHEDULING = "scheduling"
    BOOKED = "booked"
    RESCHEDULE_OFFERED = "reschedule_offered"
    CLOSED_DECLINED = "closed_declined"
    CLOSED_NO_FIT = "closed_no_fit"
    CLOSED_SUCCESS = "closed_success"


class ProspectIntent(StrEnum):
    UNKNOWN = "unknown"
    INTERESTED = "interested"
    CURIOUS = "curious"
    OBJECTING = "objecting"
    DECLINING = "declining"
    SCHEDULING = "scheduling"
    RESCHEDULING_REQUEST = "rescheduling_request"
    SILENCE_OR_AMBIGUOUS = "ambiguous"
