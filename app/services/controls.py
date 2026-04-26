from __future__ import annotations

from dataclasses import dataclass, field

from app.models import RiskTier
from app.policy import load_json


@dataclass(frozen=True)
class ControlRecommendation:
    nist_800_53: list[str] = field(default_factory=list)
    ai_rmf: list[str] = field(default_factory=list)
    template_version: str = ""


def recommend_controls(*, tier: RiskTier, answers: dict) -> ControlRecommendation:
    template = load_json("template.json")
    controls: list[str] = list(template["base_controls"][tier.value])

    additional = template["additional"]
    if answers.get("external_vendor"):
        controls.extend(additional["external_vendor"])
    if answers.get("contains_cui"):
        controls.extend(additional["contains_cui"])
    if answers.get("model_kind") == "ml_model":
        controls.extend(additional["model_kind_ml_model"])

    seen: set[str] = set()
    deduped = [c for c in controls if not (c in seen or seen.add(c))]

    return ControlRecommendation(
        nist_800_53=deduped,
        ai_rmf=template["ai_rmf"][tier.value],
        template_version=template["version"],
    )
