from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Classification, RiskTier
from app.policy import load_json

_TIER_ORDER = {RiskTier.low: 0, RiskTier.moderate: 1, RiskTier.high: 2}


@dataclass(frozen=True)
class ScoreResult:
    tier: RiskTier
    classification: Classification
    rubric_version: str
    breakdown: list[str] = field(default_factory=list)


def _matches(when: dict, answers: dict) -> bool:
    return all(answers.get(k) == v for k, v in when.items())


def score_use_case(answers: dict) -> ScoreResult:
    rubric = load_json("rubric.json")
    tier = RiskTier.low
    classification = Classification.internal
    breakdown: list[str] = []

    for rule in rubric["rules"]:
        if not _matches(rule["when"], answers):
            continue
        if "tier_min" in rule:
            candidate = RiskTier(rule["tier_min"])
            if _TIER_ORDER[candidate] > _TIER_ORDER[tier]:
                tier = candidate
                breakdown.append(f"rule {rule['id']} raised tier to {tier.value}")
        if "classification" in rule:
            classification = Classification(rule["classification"])
            breakdown.append(f"rule {rule['id']} set classification to {classification.value}")

    return ScoreResult(
        tier=tier,
        classification=classification,
        rubric_version=rubric["version"],
        breakdown=breakdown,
    )
