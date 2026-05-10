from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent.anthropic_runner import safe_completion_json
from app.agent.prompts import OUTREACH_SYSTEM_TEMPLATE
from app.config import GigConfig, Settings


class OutreachEmail(BaseModel):
    subject: str = Field(description="Concise inbox subject.")
    body: str = Field(description="Plain-text body.")


def compose_outreach(*, settings: Settings, gig: GigConfig, prospect_email: str) -> OutreachEmail:
    system = OUTREACH_SYSTEM_TEMPLATE.format(tone_key=gig.tone)
    user_payload = (
        prospect_email.split("@")[0].replace(".", " ").title()
        if "@" in prospect_email
        else "there"
    )
    user = (
        "Prospect greeting name hint: "
        + user_payload
        + "\nGig JSON:\n"
        + gig.model_dump_json()
        + '\nProduce subject and body; JSON shape matches OutreachEmail.'
    )
    return safe_completion_json(
        settings,
        system=system,
        user=user,
        schema_cls=OutreachEmail,
        temperature=0.7,
        max_tokens=2048,
    )
