from __future__ import annotations

from app.config import settings
from app.llm.base import AIArtifact, LLMClient
from app.llm.noop import NoopLLMClient


def get_llm_client(*, classification: str | None) -> LLMClient:
    if not settings.ai_features_enabled:
        return NoopLLMClient()
    if classification == "cui":
        return NoopLLMClient()
    return NoopLLMClient()  # v1: no provider implementations wired yet


__all__ = ["AIArtifact", "LLMClient", "NoopLLMClient", "get_llm_client"]
