from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.types import UtcDateTime


class ReviewPacket(SQLModel, table=True):
    __tablename__ = "review_packet"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    version: int
    markdown: str
    pdf_path: Optional[str] = None
    generated_by: int = Field(foreign_key="user.id")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
