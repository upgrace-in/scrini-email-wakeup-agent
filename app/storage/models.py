from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_prospect_email", "prospect_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prospect_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    preset_key: Mapped[str] = mapped_column(String(64), nullable=False, default="default_demo")
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    gig_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key_outreach: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )

    messages: Mapped[list[EmailMessage]] = relationship(back_populates="conversation", order_by="EmailMessage.created_at")


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("provider_message_id", name="uq_email_messages_provider_id"),
        Index("ix_email_messages_reply_to_provider", "in_reply_to_provider_id"),
        Index("ix_email_messages_conversation_id", "conversation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    provider_message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    in_reply_to_provider_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
