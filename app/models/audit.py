from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from app.models.types import UtcDateTime


class AuditLogEntry(SQLModel, table=True):
    __tablename__ = "audit_log_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    prev_hash: str
    hash: str = Field(index=True)
    actor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    action: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_id: int = Field(index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
