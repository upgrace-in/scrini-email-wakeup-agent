from __future__ import annotations

import logging
import re
from typing import Any

import resend

from app.config import Settings
from app.email.inbound_parse import NormalizedInboundEmail

log = logging.getLogger(__name__)

_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html_approx(html: str) -> str:
    text = _HTML_TAG.sub(" ", html)
    return re.sub(r"\s+", " ", text).strip()


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


def fetch_body_for_resend_email_received_webhook(
    settings: Settings, payload: dict[str, Any]
) -> NormalizedInboundEmail | None:
    """Resend `email.received` webhooks omit the body — fetch via Receiving API."""
    if payload.get("type") != "email.received":
        return None
    if not settings.resend_api_key:
        log.warning("email.received webhook but RESEND_API_KEY missing — cannot hydrate body")
        return None
    data = payload.get("data") or {}
    email_id = data.get("email_id")
    if not email_id:
        log.warning("email.received webhook missing data.email_id keys=%s", list(payload.keys()))
        return None

    resend.api_key = settings.resend_api_key
    try:
        full = resend.Emails.Receiving.get(email_id=str(email_id))
    except Exception as exc:
        detail = str(exc).lower()
        if "restricted" in detail or "only send" in detail:
            log.error(
                "resend.Receiving.get denied for email_id=%s — RESEND_API_KEY is send-only. "
                "Use an API key with Receiving/full access so inbound hooks can fetch the body.",
                email_id,
            )
        else:
            log.exception("resend.Receiving.get failed email_id=%s", email_id)
        return None

    from_raw = getattr(full, "from", None) or ""
    subject = getattr(full, "subject", "") or ""
    msg_id = getattr(full, "message_id", "") or ""

    bodies: list[str] = []
    t = getattr(full, "text", None)
    if isinstance(t, str) and t.strip():
        bodies.append(t.strip())
    html = getattr(full, "html", None)
    if isinstance(html, str) and html.strip():
        stripped = _strip_html_approx(html)
        if stripped:
            bodies.append(stripped)
    body_plain = bodies[0] if bodies else ""
    if not body_plain:
        log.warning("Received email fetched but empty text/html email_id=%s", email_id)
        return None

    headers_obj = getattr(full, "headers", None) or {}
    in_reply_to: str | None = None
    if isinstance(headers_obj, dict):
        for k, v in headers_obj.items():
            if k.lower() == "in-reply-to" and isinstance(v, str):
                in_reply_to = v.strip() or None
                break

    to_list = getattr(full, "to", None)
    first_to = to_list[0] if isinstance(to_list, list) and to_list else None

    raw = payload if isinstance(payload, dict) else {}
    merged = dict(raw)
    merged["_resend_received_hydrated_id"] = str(email_id)

    return NormalizedInboundEmail(
        from_email=str(from_raw).strip(),
        to_email=str(first_to) if first_to else None,
        subject=str(subject).strip(),
        text_body=body_plain,
        provider_message_id=msg_id or None,
        in_reply_to=in_reply_to,
        raw_payload=merged,
    )


def normalize_inbound_provider_payload(settings: Settings, payload: dict[str, Any]) -> NormalizedInboundEmail | None:
    """Parse raw webhook JSON; hydrate Resend `email.received` via API when needed."""
    n = parse_generic(payload)
    if n is not None:
        return n
    return fetch_body_for_resend_email_received_webhook(settings, payload)
