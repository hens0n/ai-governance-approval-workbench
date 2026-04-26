from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.enums import Classification, RiskTier, UseCaseStatus
from app.models.types import UtcDateTime


class UseCase(SQLModel, table=True):
    __tablename__ = "use_case"

    id: Optional[int] = Field(default=None, primary_key=True)
    sponsor_id: int = Field(foreign_key="user.id", index=True)
    title: str
    business_purpose: str
    model_name: str
    hosting: str
    status: UseCaseStatus = Field(default=UseCaseStatus.draft, index=True)
    risk_tier: Optional[RiskTier] = None
    classification: Optional[Classification] = None
    policy_template_version: str
    rubric_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
