from __future__ import annotations

from app.agent.rate_extract import merged_quoted_rates_usd_hour, supplemental_quoted_rates_usd_hour


def test_trailing_dollar_125():
    assert supplemental_quoted_rates_usd_hour("I am okay but how about 125$?") == [125.0]


def test_leading_dollar():
    assert supplemental_quoted_rates_usd_hour("Can you do $125/hr?") == [125.0]


def test_merge_dedupes_with_perception():
    assert merged_quoted_rates_usd_hour(perception_rates=[125.0], last_prospect_body="125$ firm") == [125.0]


def test_per_hour_form():
    assert supplemental_quoted_rates_usd_hour("looking for 180 / hr") == [180.0]
