from app.models import RiskTier
from app.services.controls import recommend_controls


def test_low_tier_has_base_controls_only() -> None:
    result = recommend_controls(
        tier=RiskTier.low,
        answers={"external_vendor": False, "contains_cui": False, "model_kind": "llm_api"},
    )
    assert "AC-2" in result.nist_800_53
    assert "CA-3" not in result.nist_800_53


def test_high_tier_with_vendor_adds_vendor_controls() -> None:
    result = recommend_controls(
        tier=RiskTier.high,
        answers={"external_vendor": True, "contains_cui": True, "model_kind": "llm_api"},
    )
    assert "CA-3" in result.nist_800_53
    assert "SR-3" in result.nist_800_53
    assert "SC-28" in result.nist_800_53


def test_ml_model_adds_si_7() -> None:
    result = recommend_controls(
        tier=RiskTier.moderate,
        answers={"external_vendor": False, "contains_cui": False, "model_kind": "ml_model"},
    )
    assert "SI-7" in result.nist_800_53
