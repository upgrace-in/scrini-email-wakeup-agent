from __future__ import annotations

import logging

import resend
from pydantic import BaseModel

from app.config import Settings

log = logging.getLogger(__name__)


class SentEmailReceipt(BaseModel):
    provider_message_id: str | None = None
    http_status: int | None = None


def send_outbound(*, settings: Settings, to_email: str, subject: str, body: str) -> SentEmailReceipt:
    if not settings.outbound_to_email_allowed(to_email):
        raise RuntimeError(
            f"Sandbox allowlist: refusing to send to {to_email!r}. "
            "Set SANDBOX_ALLOWED_TO_EMAILS in .env or add this address (comma-separated)."
        )

    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is required — outbound email is always sent via Resend.")

    # Official Resend Python SDK (same pattern as https://resend.com/docs/send-with-python )
    resend.api_key = settings.resend_api_key
    try:
        text_body = body.rstrip()
        reply_addr = (settings.email_reply_to or "").strip()
        if reply_addr:
            # Visible hint: Reply-To / Cc easy to miss in Gmail; mirrors Resend Receiving.
            if reply_addr.lower() not in text_body.lower():
                text_body += f"\n\n—\nReply or Reply all so a copy reaches: {reply_addr}"

        cc_list: list[str] = []
        for part in (settings.email_cc or "").split(","):
            p = part.strip()
            if p and p.lower() not in {x.lower() for x in cc_list}:
                cc_list.append(p)
        if (
            settings.mirror_reply_to_in_cc
            and reply_addr
            and reply_addr.lower() not in {x.lower() for x in cc_list}
        ):
            cc_list.append(reply_addr)

        payload: dict[str, object] = {
            "from": settings.email_from,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
        }
        if reply_addr:
            payload["reply_to"] = [reply_addr]
        if cc_list:
            payload["cc"] = cc_list

        r = resend.Emails.send(payload)
    except Exception as exc:
        log.exception("resend.send_failed to=%s subject=%s", to_email, subject)
        raise RuntimeError("Resend send failed") from exc

    mid = getattr(r, "id", None)
    log.info("resend outbound accepted | to=%s subject=%s provider_message_id=%s", to_email, subject, mid)
    return SentEmailReceipt(provider_message_id=mid, http_status=200)
