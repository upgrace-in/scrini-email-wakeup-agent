from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from app.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_fence_open = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_fence_close = re.compile(r"\s*```\s*\Z")


class LLMStructuredError(RuntimeError):
    pass


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    s = _fence_open.sub("", s, count=1)
    s = _fence_close.sub("", s, count=1)
    return s.strip()


def _text_from_message_content(content: object) -> str:
    parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if hasattr(block, "text") and getattr(block, "text", None):
                parts.append(str(block.text))
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    return "".join(parts).strip()


def safe_completion_json(
    settings: Settings,
    *,
    system: str,
    user: str,
    schema_cls: type[T],
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> T:
    """Ask Claude for JSON matching ``schema_cls`` (validated after parse)."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    schema_hint = json.dumps(schema_cls.model_json_schema(), indent=2)
    if len(schema_hint) > 14_000:
        schema_hint = schema_hint[:14_000] + "\n... (truncated)"
    full_user = (
        f"{user}\n\n"
        "Respond with a single JSON object only (no markdown code fences, no commentary). "
        "The object must be parseable as JSON and conform to this JSON Schema:\n"
        f"{schema_hint}"
    )
    combined_system = (
        system
        + "\n\nHard rule: reply with exactly one JSON object matching the user's schema — nothing else."
    )
    try:
        msg = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=combined_system,
            messages=[{"role": "user", "content": full_user}],
        )
    except Exception as exc:
        log.exception("anthropic.messages_failed model=%s", settings.anthropic_model)
        raise LLMStructuredError("LLM completion failed") from exc

    text = _text_from_message_content(msg.content)
    text = _strip_json_fence(text)
    if not text:
        raise LLMStructuredError("Empty model response")
    try:
        return schema_cls.model_validate_json(text)
    except Exception:
        try:
            return schema_cls.model_validate(json.loads(text))
        except Exception as exc:
            log.warning("anthropic.json_parse_failed snippet=%s", text[:240])
            raise LLMStructuredError("Could not parse model JSON") from exc
