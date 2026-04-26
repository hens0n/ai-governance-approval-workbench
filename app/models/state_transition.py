from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.enums import UseCaseStatus
from app.models.types import UtcDateTime


class StateTransition(SQLModel, table=True):
    __tablename__ = "state_transition"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    from_state: UseCaseStatus
    to_state: UseCaseStatus
    actor_id: int = Field(foreign_key="user.id")
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
