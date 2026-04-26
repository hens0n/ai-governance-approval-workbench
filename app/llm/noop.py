from __future__ import annotations

from app.llm.base import AIArtifact, _now


class NoopLLMClient:
    model: str = "noop"

    def summarize_intake(self, *, use_case_title: str, intake: dict) -> AIArtifact:
        return AIArtifact(
            content="AI features disabled for this deployment or case.",
            model=self.model,
            generated_at=_now(),
        )

    def extract_red_flags(self, *, narrative: str) -> list[AIArtifact]:
        return []

    def suggest_controls(self, *, use_case_title: str, intake: dict) -> list[AIArtifact]:
        return []
