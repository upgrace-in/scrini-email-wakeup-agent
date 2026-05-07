from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import MessageDirection
from app.domain.thread_state import ConversationState, parse_state, serialize_state
from app.storage.models import Conversation, EmailMessage


@dataclass
class ConversationWithMessages:
    conversation: Conversation
    messages: list[EmailMessage]


class ConversationRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, conversation_id: str) -> Conversation | None:
        return self._session.get(Conversation, conversation_id)

    def get_with_messages(self, conversation_id: str) -> ConversationWithMessages | None:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        conv = self._session.scalar(stmt)
        if conv is None:
            return None
        return ConversationWithMessages(conversation=conv, messages=list(conv.messages))

    def find_by_idempotency(self, key: str) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.idempotency_key_outreach == key).limit(1)
        return self._session.scalar(stmt)

    def find_by_reply_to_provider_id(self, in_reply_to: str) -> Conversation | None:
        if not (in_reply_to or "").strip():
            return None
        stmt = (
            select(Conversation)
            .join(EmailMessage, EmailMessage.conversation_id == Conversation.id)
            .where(EmailMessage.provider_message_id == in_reply_to)
            .limit(1)
        )
        return self._session.scalar(stmt)

    def find_latest_from_prospect(self, prospect_email: str) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.prospect_email == prospect_email)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        return self._session.scalar(stmt)

    def create_outreach_thread(
        self,
        *,
        prospect_email: str,
        subject: str,
        preset_key: str,
        gig_snapshot: dict,
        state: ConversationState,
        idempotency_key: str | None,
    ) -> Conversation:
        row = Conversation(
            prospect_email=prospect_email,
            subject=subject,
            preset_key=preset_key,
            gig_snapshot_json=gig_snapshot,
            state_json=serialize_state(state),
            idempotency_key_outreach=idempotency_key,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def append_message(
        self,
        *,
        conversation_id: str,
        direction: MessageDirection,
        body_text: str,
        subject: str,
        provider_message_id: str | None,
        in_reply_to_provider_id: str | None,
        metadata: dict | None = None,
    ) -> EmailMessage:
        msg = EmailMessage(
            conversation_id=conversation_id,
            direction=direction.value,
            body_text=body_text,
            subject=subject,
            provider_message_id=normalize_header_id(provider_message_id),
            in_reply_to_provider_id=normalize_header_id(in_reply_to_provider_id),
            metadata_json=metadata or {},
        )
        self._session.add(msg)
        self._session.flush()
        return msg

    def load_state(self, conv: Conversation) -> ConversationState:
        return parse_state(conv.state_json)

    def save_state(self, conv: Conversation, state: ConversationState) -> None:
        conv.state_json = serialize_state(state)
        self._session.add(conv)


def normalize_header_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    trimmed = str(raw).strip().strip("<>")
    return trimmed or None


def transcript_for_prompt(messages: list[EmailMessage]) -> str:
    lines: list[str] = []
    for m in sorted(messages, key=lambda x: x.created_at):
        who = "AGENT" if m.direction == MessageDirection.OUTBOUND.value else "PROSPECT"
        subj = (m.subject or "").strip()
        hdr = who if not subj else f"{who} [subject={subj}]"
        lines.append(f"{hdr}:\n{m.body_text.strip()}\n")
    return "\n---\n".join(lines)


def message_exists_by_provider_id(session: Session, provider_message_id: str | None) -> bool:
    pid = normalize_header_id(provider_message_id)
    if not pid:
        return False
    stmt = select(EmailMessage.id).where(EmailMessage.provider_message_id == pid).limit(1)
    return session.scalar(stmt) is not None
