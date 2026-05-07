from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.agent.prompts import OUTREACH_SYSTEM_TEMPLATE
from app.config import GigConfig, Settings
from openai import OpenAI


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
    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.7,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Prospect greeting name hint: "
                    + user_payload
                    + "\n Gig JSON:\n"
                    + gig.model_dump_json()
                    + '\nRespond JSON only matching {"subject": "...", "body": "..."}'
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    raw = completion.choices[0].message.content or "{}"
    try:
        return OutreachEmail.model_validate_json(raw)
    except Exception:
        return OutreachEmail.model_validate(json.loads(raw))
