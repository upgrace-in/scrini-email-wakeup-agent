"""Deterministic hourly-rate hints when the perception model misses odd formats ($125 vs 125$)."""
from __future__ import annotations

import re

# Ignore ISO years and common stub slot years accidentally appearing in prose.
_YEAR_LIKE = re.compile(r"\b20[12]\d\b")

_RAW_PATTERNS: list[re.Pattern[str]] = [
    # $125, $125/hr, $125 / hr
    re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?=\s*(?:usd|usd/hr|\$|/|\s*hr\b|\s*h\b|[.,!?)\]]|\s|$))", re.I),
    # Trailing-dollar: "125$" or "about 125 $"
    re.compile(r"(?<![$\w])(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*\$(?!\w)", re.I),
    # 125/hr, 125 per hour (avoid matching lone years)
    re.compile(
        r"(?<![$\w])(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?:/\s*hr\b|per\s*hour\b|\s*h\b(?=\s|\.|,))",
        re.I,
    ),
]


def _parse_money_token(tok: str) -> float | None:
    cleaned = tok.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        v = float(cleaned)
    except ValueError:
        return None
    # Loose contractor band; tweak if gigs go outside this.
    if 25.0 <= v <= 2000.0:
        return v
    return None


def supplemental_quoted_rates_usd_hour(text: str | None) -> list[float]:
    """Pull numeric hourly mentions from raw email text."""
    if not (text or "").strip():
        return []
    clipped = _YEAR_LIKE.sub("", text)
    seen: set[float] = set()
    out: list[float] = []
    for rx in _RAW_PATTERNS:
        for m in rx.finditer(clipped):
            val = _parse_money_token(m.group(1))
            if val is None:
                continue
            if val not in seen:
                seen.add(val)
                out.append(val)
    return sorted(out)


def merged_quoted_rates_usd_hour(*, perception_rates: list[float], last_prospect_body: str | None) -> list[float]:
    extra = supplemental_quoted_rates_usd_hour(last_prospect_body)
    return sorted({float(x) for x in (*perception_rates, *extra)})
