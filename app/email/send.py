from __future__ import annotations

import logging
import uuid

import httpx

from pydantic import BaseModel, Field

from app.config import Settings

log = logging.getLogger(__name__)


class SentEmailReceipt(BaseModel):
    provider_message_id: str | None = None
    mock: bool = Field(default=False)
    http_status: int | None = None


def send_outbound(*, settings: Settings, to_email: str, subject: str, body: str) -> SentEmailReceipt:
    if settings.mock_email:
        mid = f"mock-{uuid.uuid4()}"
        log.info("MOCK email | to=%s | subject=%s | id=%s", to_email, subject, mid)
        log.debug("MOCK body:\n%s", body)
        return SentEmailReceipt(provider_message_id=mid, mock=True, http_status=200)

    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY required when MOCK_EMAIL=false")

    payload = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post("https://api.resend.com/emails", json=payload, headers=headers)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.error("resend.send_failed status=%s body=%s", resp.status_code, resp.text)
        raise RuntimeError("Resend send failed") from exc

    data = resp.json()
    message_id = data.get("id")
    return SentEmailReceipt(provider_message_id=message_id, mock=False, http_status=resp.status_code)
