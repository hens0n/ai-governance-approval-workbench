from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.types import UtcDateTime


class IntakeAnswer(SQLModel, table=True):
    __tablename__ = "intake_answer"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    question_key: str = Field(index=True)
    answer_value: dict = Field(sa_column=Column(JSON))
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
