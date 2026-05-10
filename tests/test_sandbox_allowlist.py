from __future__ import annotations

from app.config import email_matches_sandbox_allowlist


def test_allowlist_empty_allows_any():
    assert email_matches_sandbox_allowlist(None, "anyone@example.com") is True
    assert email_matches_sandbox_allowlist("", "anyone@example.com") is True
    assert email_matches_sandbox_allowlist("   ", "anyone@example.com") is True


def test_allowlist_single_match_is_case_insensitive():
    raw = "gptprince4274@gmail.com"
    assert email_matches_sandbox_allowlist(raw, "Gptprince4274@gmail.com") is True
    assert email_matches_sandbox_allowlist(raw, "other@gmail.com") is False


def test_allowlist_accepts_comma_separated():
    raw = "a@x.com , b@y.com"
    assert email_matches_sandbox_allowlist(raw, "b@y.com") is True
    assert email_matches_sandbox_allowlist(raw, "c@z.com") is False
