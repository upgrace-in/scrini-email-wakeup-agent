from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizedInboundEmail(BaseModel):
    """Provider-agnostic normalized inbound message."""

    from_email: str
    to_email: str | None = None
    subject: str = ""
    text_body: str
    provider_message_id: str | None = None
    in_reply_to: str | None = None
    raw_payload: dict = Field(default_factory=dict)
