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
    budget_target_usd_hour: float | None = Field(
        default=None,
        description="Opening anchor we prefer to land at; defaults to 0.85 * ceiling.",
    )
    budget_floor_usd_hour: float | None = Field(
        default=None,
        description="Minimum we'd pay if prospect pushes very low; defaults to 0.70 * ceiling.",
    )
    concession_step_usd_hour: float | None = Field(
        default=None,
        description="Max increment when countering; defaults to max(5, 0.05 * ceiling).",
    )
    negotiation_max_rounds: int = Field(
        default=3,
        ge=1,
        description="How many counters we send when prospect stays above ceiling before walking away.",
    )
    negotiation_style: Literal["aggressive", "balanced", "accommodating"] = Field(
        default="balanced",
        description="Tone for negotiation moves; 'aggressive' = slower concessions, 'accommodating' = larger steps.",
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

    @field_validator("budget_target_usd_hour", "budget_floor_usd_hour", "concession_step_usd_hour")
    @classmethod
    def non_negative_optional(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if v < 0:
            raise ValueError("must be non-negative")
        return v

    def effective_target_usd_hour(self) -> float | None:
        if self.budget_target_usd_hour is not None:
            return self.budget_target_usd_hour
        if self.budget_ceiling_usd_hour is None:
            return None
        return round(self.budget_ceiling_usd_hour * 0.85, 2)

    def effective_floor_usd_hour(self) -> float | None:
        if self.budget_floor_usd_hour is not None:
            return self.budget_floor_usd_hour
        if self.budget_ceiling_usd_hour is None:
            return None
        return round(self.budget_ceiling_usd_hour * 0.70, 2)

    def effective_concession_step_usd_hour(self) -> float:
        if self.concession_step_usd_hour is not None and self.concession_step_usd_hour > 0:
            return float(self.concession_step_usd_hour)
        if self.budget_ceiling_usd_hour is None:
            return 5.0
        return max(5.0, round(self.budget_ceiling_usd_hour * 0.05, 2))


def email_matches_sandbox_allowlist(allowlist_csv: str | None, to_email: str) -> bool:
    """If allowlist_csv is empty, all addresses are allowed."""
    raw = (allowlist_csv or "").strip()
    if not raw:
        return True
    allowed = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return to_email.strip().lower() in allowed


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
        "budget_target_usd_hour": 95.0,
        "budget_floor_usd_hour": 80.0,
        "concession_step_usd_hour": 10.0,
        "negotiation_max_rounds": 3,
        "negotiation_style": "balanced",
        "timezone_hint": "Americas-friendly (ET anchor)",
        "tone": "friendly_professional",
        "scheduling_cta": "If this sounds aligned, I can share two Cal slots — does Tue 2pm ET or Wed 4:30pm ET work?",
    },
    "high_budget": {
        "gig_title": "Staff engineer — agent platform",
        "gig_summary": "Greenfield orchestration layer for multi-step agents with human-in-the-loop.",
        "role_focus": ["distributed systems", "LLM infra", "TypeScript/Python"],
        "budget_ceiling_usd_hour": 200.0,
        "budget_target_usd_hour": 170.0,
        "budget_floor_usd_hour": 140.0,
        "concession_step_usd_hour": 15.0,
        "negotiation_max_rounds": 3,
        "negotiation_style": "balanced",
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

    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-6",
        alias="ANTHROPIC_MODEL",
        description="Claude model id for Messages API (e.g. claude-sonnet-4-6, claude-opus-4-6).",
    )

    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    email_from: str = Field(default="agent@example.com", alias="EMAIL_FROM")
    email_reply_to: str | None = Field(
        default=None,
        alias="EMAIL_REPLY_TO",
        description="Reply-To address on outbound mail; use *@<team>.resend.app so replies hit Resend Receiving.",
    )
    email_cc: str | None = Field(
        default=None,
        alias="EMAIL_CC",
        description="Extra Cc recipients (comma-separated). Resend test mode rejects Cc unless all are your verified inbox.",
    )
    mirror_reply_to_in_cc: bool = Field(
        default=False,
        alias="EMAIL_MIRROR_REPLY_TO_IN_CC",
        description="Also Cc EMAIL_REPLY_TO. OFF by default: Resend + onboarding@resend.dev only allows sending to your test Gmail — Cc counts as recipients and triggers 422.",
    )
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

    sandbox_allowed_to_emails: str | None = Field(
        default=None,
        alias="SANDBOX_ALLOWED_TO_EMAILS",
        description="If set, outbound / outreach may only use these addresses (comma-separated, case-insensitive).",
    )

    def outbound_to_email_allowed(self, to_email: str) -> bool:
        return email_matches_sandbox_allowlist(self.sandbox_allowed_to_emails, to_email)

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
