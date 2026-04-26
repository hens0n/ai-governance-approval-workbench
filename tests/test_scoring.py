from app.models import Classification, RiskTier
from app.services.scoring import score_use_case


def test_low_tier_internal_no_pii() -> None:
    answers = {
        "data_types": ["internal_policy_docs"],
        "contains_pii": False,
        "contains_cui": False,
        "hosting": "agency-azure",
        "model_kind": "llm_api",
        "external_vendor": False,
    }
    result = score_use_case(answers)
    assert result.tier == RiskTier.low
    assert result.classification == Classification.internal
    assert result.rubric_version == "v1"


def test_high_tier_on_cui_plus_external_vendor() -> None:
    answers = {
        "data_types": ["contract_terms", "vendor_identities"],
        "contains_pii": False,
        "contains_cui": True,
        "hosting": "vendor_cloud",
        "model_kind": "llm_api",
        "external_vendor": True,
    }
    result = score_use_case(answers)
    assert result.tier == RiskTier.high
    assert result.classification == Classification.cui


def test_moderate_tier_on_pii_internal() -> None:
    answers = {
        "data_types": ["employee_qna"],
        "contains_pii": True,
        "contains_cui": False,
        "hosting": "agency-azure",
        "model_kind": "llm_api",
        "external_vendor": False,
    }
    result = score_use_case(answers)
    assert result.tier == RiskTier.moderate
    assert result.classification == Classification.sensitive


def test_result_includes_breakdown_for_auditability() -> None:
    answers = {
        "data_types": [],
        "contains_pii": False,
        "contains_cui": True,
        "hosting": "agency-azure",
        "model_kind": "ml_model",
        "external_vendor": False,
    }
    result = score_use_case(answers)
    assert any("cui" in factor.lower() for factor in result.breakdown)
