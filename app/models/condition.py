from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.enums import ConditionStatus
from app.models.types import UtcDateTime


class Condition(SQLModel, table=True):
    __tablename__ = "condition"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    name: str
    description: str
    status: ConditionStatus = Field(default=ConditionStatus.proposed)
    source_review_id: Optional[int] = Field(default=None, foreign_key="review.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
    satisfied_at: Optional[datetime] = Field(default=None, sa_column=Column(UtcDateTime()))
