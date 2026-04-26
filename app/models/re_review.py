from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.enums import ReReviewTrigger
from app.models.types import UtcDateTime


class ReReview(SQLModel, table=True):
    __tablename__ = "re_review"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    due_date: datetime = Field(sa_column=Column(UtcDateTime()))
    trigger: ReReviewTrigger = Field(default=ReReviewTrigger.scheduled)
    completed_at: Optional[datetime] = Field(default=None, sa_column=Column(UtcDateTime()))
    status: str = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
