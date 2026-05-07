from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class OutreachPayload(BaseModel):
    prospect_email: EmailStr
    preset_key: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)
    subject_hint: str | None = Field(default=None, max_length=900)


class SimulatedInboundPayload(BaseModel):
    text_body: str = Field(..., min_length=1)
    subject: str = Field(default="", max_length=998)
    provider_message_id: str | None = Field(default=None, max_length=512)
    in_reply_to_provider_id: str | None = Field(default=None, max_length=512)
