from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMStructuredError(RuntimeError):
    pass


def _completion_json(settings: Settings, *, system: str, user: str, schema_cls: type[T]) -> T:
    client = OpenAI(api_key=settings.openai_api_key)
    schema_obj: dict[str, Any] = {
        "name": schema_cls.__name__,
        "schema": schema_cls.model_json_schema(),
    }
    try:
        resp = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_schema", "json_schema": schema_obj},
        )
    except Exception as exc:
        log.exception("openai.completion_failed model=%s", settings.openai_model)
        raise LLMStructuredError("LLM completion failed") from exc

    content = resp.choices[0].message.content or ""
    return schema_cls.model_validate_json(content)


def safe_completion_json(settings: Settings, *, system: str, user: str, schema_cls: type[T]) -> T:
    try:
        return _completion_json(settings, system=system, user=user, schema_cls=schema_cls)
    except Exception:
        content = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            messages=[
                {"role": "system", "content": system + "\nOutput valid JSON matching the user's schema hints."},
                {"role": "user", "content": user + "\nReturn JSON only matching expected fields."},
            ],
            response_format={"type": "json_object"},
        ).choices[0].message.content or "{}"
        return schema_cls.model_validate(json.loads(content))
