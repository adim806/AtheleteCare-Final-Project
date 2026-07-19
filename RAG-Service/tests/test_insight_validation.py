"""Unit tests for insight validation (no LLM required)."""

from app.rag_engine import INSIGHT_FALLBACK, validate_insight


def test_validate_insight_accepts_good_clinical_text():
    insight = (
        "Based on Document 1 (calf tear case), sudden posterior calf pain during "
        "sprinting is consistent with gastrocnemius tear. Return-to-play around "
        "8 weeks aligns with the documented club case."
    )
    is_valid, reason = validate_insight(insight)
    assert is_valid is True
    assert reason == ""


def test_validate_insight_rejects_placeholder():
    insight = '{"protocol": "<your relevant protocol reference here>"}'
    is_valid, reason = validate_insight(insight)
    assert is_valid is False
    assert "invalid pattern" in reason


def test_validate_insight_rejects_too_short():
    is_valid, reason = validate_insight("Too short.")
    assert is_valid is False
    assert "shorter than" in reason


def test_validate_insight_accepts_fallback_message():
    is_valid, reason = validate_insight(INSIGHT_FALLBACK)
    assert is_valid is True
