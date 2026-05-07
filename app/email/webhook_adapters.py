from __future__ import annotations

import logging
from typing import Any

from app.email.inbound_parse import NormalizedInboundEmail

log = logging.getLogger(__name__)


def parse_resend_inbound(payload: dict[str, Any]) -> NormalizedInboundEmail | None:
    """
    Normalize Resend-style inbound payloads.

    Docs evolve — we accept permissive unions of common keys.
    """
    data = payload.get("data") or payload.get("payload") or payload
    headers = data.get("headers") or {}

    def _header(name_variants: tuple[str, ...]) -> str | None:
        for key in headers:
            lk = key.lower()
            if lk in tuple(n.lower() for n in name_variants):
                v = headers.get(key)
                if isinstance(v, list) and v:
                    return str(v[0])
                return str(v) if v is not None else None
        return None

    from_email = (
        data.get("from")
        or _header(("From",))
        or (data.get("from_email") if isinstance(data.get("from_email"), str) else None)
        or ""
    )
    subject = data.get("subject") or ""

    bodies = []
    html = data.get("html") or ""
    text = data.get("text") or ""
    if text:
        bodies.append(text)
    elif isinstance(data.get("body"), dict):
        if data["body"].get("plain"):
            bodies.append(str(data["body"]["plain"]))
        elif data["body"].get("text"):
            bodies.append(str(data["body"]["text"]))
    if html:
        bodies.append(html)
    body_plain = bodies[0] if bodies else ""

    msg_id = data.get("message_id") or _header(("Message-ID", "Message-Id")) or ""
    reply_to_hdr = (
        data.get("in_reply_to")
        or data.get("inReplyTo")
        or _header(("In-Reply-To",))
        or _header(("References",))  # last resort heuristic left to orchestrator repo
        or ""
    ).strip()

    if not body_plain.strip():
        log.warning("Inbound parse yielded empty body payload_keys=%s", list(data.keys())[:24])
        return None

    return NormalizedInboundEmail(
        from_email=str(from_email).strip(),
        to_email=(str(data.get("to")) if data.get("to") else None),
        subject=str(subject).strip(),
        text_body=body_plain.strip(),
        provider_message_id=msg_id or None,
        in_reply_to=reply_to_hdr or None,
        raw_payload=payload,
    )


def parse_mailgun_stub(payload: dict[str, Any]) -> NormalizedInboundEmail | None:
    """Minimal Mailgun forward route shape for interoperability."""

    if "sender" in payload:
        sender = payload.get("sender") or ""
        subject = payload.get("subject") or ""
        body = payload.get("body-plain") or payload.get("stripped-text") or ""
        if not sender or not body:
            return None
        msg_id = payload.get("Message-Id") or payload.get("message-id")
        in_reply = payload.get("In-Reply-To") or payload.get("in-reply-to")
        return NormalizedInboundEmail(
            from_email=str(sender).strip(),
            to_email=str(payload.get("recipient") or "") or None,
            subject=str(subject).strip(),
            text_body=str(body).strip(),
            provider_message_id=str(msg_id) if msg_id else None,
            in_reply_to=str(in_reply) if in_reply else None,
            raw_payload=payload,
        )
    return None


def parse_generic(payload: dict[str, Any]) -> NormalizedInboundEmail | None:
    return parse_resend_inbound(payload) or parse_mailgun_stub(payload)
