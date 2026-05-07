from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GigConfig(BaseModel):
    """Configurable gig + negotiation envelope (not hard-coded in prompts as literals)."""

    gig_title: str
    gig_summary: str
    role_focus: list[str]
    budget_ceiling_usd_hour: float | None = Field(
        default=None,
        description="Hard ceiling for negotiated hourly rate in USD.",
    )
    timezone_hint: str = "UTC"
    tone: Literal["friendly_professional", "direct_concise", "warm_verbose"] = "friendly_professional"
    scheduling_cta: str = "I'd love to find 25 minutes this week."

    @field_validator("budget_ceiling_usd_hour")
    @classmethod
    def non_negative_budget(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if v < 0:
            raise ValueError("budget ceiling must be non-negative")
        return v


_AGENT_PRESETS: dict[str, dict] = {
    "default_demo": {
        "gig_title": "Senior AI tooling engineer — contract kickoff",
        "gig_summary": (
            "We're building autonomous sales-assist workflows (email + CRM). "
            "Looking for someone who can ship reliable LLM-backed services, "
            "own evals, and partner with product on UX for semi-autonomous agents."
        ),
        "role_focus": [
            "Python/FastAPI or Node services",
            "prompt + tool orchestration",
            "observability and safety guardrails",
        ],
        "budget_ceiling_usd_hour": 120.0,
        "timezone_hint": "Americas-friendly (ET anchor)",
        "tone": "friendly_professional",
        "scheduling_cta": "If this sounds aligned, I can share two Cal slots — does Tue 2pm ET or Wed 4:30pm ET work?",
    },
    "high_budget": {
        "gig_title": "Staff engineer — agent platform",
        "gig_summary": "Greenfield orchestration layer for multi-step agents with human-in-the-loop.",
        "role_focus": ["distributed systems", "LLM infra", "TypeScript/Python"],
        "budget_ceiling_usd_hour": 200.0,
        "timezone_hint": "EU or US East",
        "tone": "direct_concise",
        "scheduling_cta": "Pick a slot: I'll send calendar holds.",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT"))

    database_url: str = Field(default="sqlite:///./data/wakeup.db", alias="DATABASE_URL")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    mock_email: bool = Field(default=True, alias="MOCK_EMAIL")
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    email_from: str = Field(default="agent@example.com", alias="EMAIL_FROM")
    email_reply_domain: str = Field(default="example.com", alias="EMAIL_REPLY_DOMAIN")

    webhook_secret: str | None = Field(default=None, alias="WEBHOOK_SECRET")

    calendar_mode: Literal["stub", "noop"] = Field(default="stub", alias="CALENDAR_MODE")

    stub_available_slots_iso: str = Field(
        default=(
            "2026-05-12T14:00:00+00:00,"
            "2026-05-13T16:30:00+00:00,"
            "2026-05-14T10:00:00+00:00"
        ),
        alias="STUB_AVAILABLE_SLOTS_ISO",
    )

    default_agent_preset: str = Field(default="default_demo", alias="DEFAULT_AGENT_PRESET")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    def preset_gig_config(self, preset_key: str | None = None) -> GigConfig:
        key = preset_key or self.default_agent_preset
        raw = _AGENT_PRESETS.get(key)
        if raw is None:
            raise ValueError(f"Unknown agent preset: {key!r}. Known: {list(_AGENT_PRESETS)}")
        return GigConfig.model_validate(raw)

    def stub_slot_list(self) -> list[str]:
        return [s.strip() for s in self.stub_available_slots_iso.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def list_presets() -> dict[str, dict]:
    return json.loads(json.dumps(_AGENT_PRESETS))
