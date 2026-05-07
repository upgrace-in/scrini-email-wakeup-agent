from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.orchestrator import EmailAgentOrchestrator
from app.api.deps import db_session_dependency, orchestrator_factory
from app.api.schemas import OutreachPayload, SimulatedInboundPayload
from app.config import Settings, get_settings
from app.domain.enums import MessageDirection
from app.email.webhook_adapters import parse_generic
from app.storage.repository import ConversationRepository, message_exists_by_provider_id, normalize_header_id

log = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    ok: bool = True


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()


class OutreachResponse(BaseModel):
    conversation_id: str
    mock_email: bool


def get_settings_dep() -> Settings:
    return get_settings()


@router.post("/v1/agent/outreach", response_model=OutreachResponse)
def start_outreach(
    payload: OutreachPayload,
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(get_settings_dep),
):
    orchestrator = orchestrator_factory(settings, ConversationRepository(session))
    conv, receipt, _outreach = orchestrator.initiate_outreach(
        prospect_email=str(payload.prospect_email),
        preset_key=payload.preset_key,
        idempotency_key=payload.idempotency_key,
        subject_hint=payload.subject_hint,
    )
    _ = _outreach
    return OutreachResponse(conversation_id=conv.id, mock_email=receipt.mock)


class ConversationEnvelope(BaseModel):
    id: str
    prospect_email: str
    subject: str
    preset_key: str
    gig_title: Any
    state: dict[str, Any]
    messages: list[dict[str, Any]]


@router.get("/internal/conversations/{conversation_id}", response_model=ConversationEnvelope)
def get_conversation_snapshot(
    conversation_id: str,
    session: Session = Depends(db_session_dependency),
):
    repo = ConversationRepository(session)
    bundle = repo.get_with_messages(conversation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="not found")

    msgs = sorted(bundle.messages, key=lambda m: m.created_at)
    return ConversationEnvelope(
        id=bundle.conversation.id,
        prospect_email=bundle.conversation.prospect_email,
        subject=bundle.conversation.subject,
        preset_key=bundle.conversation.preset_key,
        gig_title=bundle.conversation.gig_snapshot_json.get("gig_title"),
        state=bundle.conversation.state_json,
        messages=[
            {
                "direction": m.direction,
                "subject": m.subject,
                "body_text": m.body_text,
                "provider_message_id": m.provider_message_id,
                "in_reply_to_provider_id": m.in_reply_to_provider_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
    )


class InboundWebhookAck(BaseModel):
    accepted: bool
    conversation_id: str | None = None


def _resolve_conversation(
    repo: ConversationRepository,
    *,
    prospect_email: str,
    in_reply_to: str | None,
):
    normalized_reply = normalize_header_id(in_reply_to)
    conv = repo.find_by_reply_to_provider_id(normalized_reply or "") if normalized_reply else None
    if conv is not None:
        return conv
    return repo.find_latest_from_prospect(prospect_email.strip())


@router.post("/webhooks/email/inbound", response_model=InboundWebhookAck)
def inbound_email_provider_webhook(
    payload: dict[str, Any],
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(get_settings_dep),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    if settings.webhook_secret and x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook authentication")

    inbound = parse_generic(payload)
    if inbound is None:
        raise HTTPException(status_code=400, detail="Could not normalize inbound payload")

    repo = ConversationRepository(session)
    mid = normalize_header_id(inbound.provider_message_id)
    conv = _resolve_conversation(repo, prospect_email=inbound.from_email, in_reply_to=inbound.in_reply_to)
    if conv is None:
        raise HTTPException(status_code=422, detail="No matching conversation/thread anchor")

    if mid and message_exists_by_provider_id(session, mid):
        log.info("inbound_duplicate provider_message_id=%s conversation=%s", mid, conv.id)
        return InboundWebhookAck(accepted=False, conversation_id=str(conv.id))

    orchestrator = orchestrator_factory(settings, repo)
    repo.append_message(
        conversation_id=str(conv.id),
        direction=MessageDirection.INBOUND,
        body_text=inbound.text_body,
        subject=inbound.subject or conv.subject,
        provider_message_id=mid,
        in_reply_to_provider_id=normalize_header_id(inbound.in_reply_to),
        metadata={"source": "inbound_provider_webhook"},
    )
    orch_receipt = orchestrator.process_conversation(str(conv.id))
    log.info("inbound_processed conversation=%s phase=%s", conv.id, orch_receipt.phase_after)
    return InboundWebhookAck(accepted=True, conversation_id=str(conv.id))


@router.post("/internal/simulations/{conversation_id}/inbound", response_model=InboundWebhookAck)
def simulate_inbound(
    conversation_id: str,
    payload: SimulatedInboundPayload,
    session: Session = Depends(db_session_dependency),
    settings: Settings = Depends(get_settings_dep),
):
    repo = ConversationRepository(session)
    conv = repo.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404)
    mid = normalize_header_id(payload.provider_message_id)
    if mid and message_exists_by_provider_id(session, mid):
        return InboundWebhookAck(accepted=False, conversation_id=conversation_id)

    orchestrator = orchestrator_factory(settings, repo)
    repo.append_message(
        conversation_id=conversation_id,
        direction=MessageDirection.INBOUND,
        body_text=payload.text_body.strip(),
        subject=payload.subject or conv.subject,
        provider_message_id=mid,
        in_reply_to_provider_id=normalize_header_id(payload.in_reply_to_provider_id),
        metadata={"source": "simulate_inbound"},
    )
    orch = orchestrator.process_conversation(conversation_id)
    log.info("simulated_inbound_processed conversation=%s phase=%s", conversation_id, orch.phase_after)
    return InboundWebhookAck(accepted=True, conversation_id=conversation_id)
