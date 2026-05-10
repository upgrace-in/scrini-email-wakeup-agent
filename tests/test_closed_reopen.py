from __future__ import annotations

from app.agent.orchestrator import _prospect_reopens_closed_thread
from app.agent.schemas import PerceptionResult
from app.domain.enums import ProspectIntent


def _p(**kwargs) -> PerceptionResult:
    base = dict(
        intent=ProspectIntent.UNKNOWN,
        is_hard_decline=False,
        rationale="x",
        quoted_rates_usd_hour=[],
    )
    base.update(kwargs)
    return PerceptionResult(**base)


def test_reopen_scheduling_like():
    assert _prospect_reopens_closed_thread(_p(intent=ProspectIntent.RESCHEDULING_REQUEST)) is True


def test_reopen_hard_decline_blocks():
    assert _prospect_reopens_closed_thread(_p(intent=ProspectIntent.INTERESTED, is_hard_decline=True)) is False


def test_reopen_declining_intent_blocks():
    assert _prospect_reopens_closed_thread(_p(intent=ProspectIntent.DECLINING)) is False


def test_reopen_ambiguous_default_false():
    assert _prospect_reopens_closed_thread(_p(intent=ProspectIntent.SILENCE_OR_AMBIGUOUS)) is False


def test_reopen_interested():
    assert _prospect_reopens_closed_thread(_p(intent=ProspectIntent.INTERESTED)) is True
