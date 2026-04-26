from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class AIArtifact:
    content: str
    model: str
    generated_at: datetime
    advisory: bool = True


class LLMClient(Protocol):
    def summarize_intake(self, *, use_case_title: str, intake: dict) -> AIArtifact: ...
    def extract_red_flags(self, *, narrative: str) -> list[AIArtifact]: ...
    def suggest_controls(self, *, use_case_title: str, intake: dict) -> list[AIArtifact]: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)
