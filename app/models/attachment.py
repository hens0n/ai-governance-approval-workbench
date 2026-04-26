from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.enums import AttachmentKind
from app.models.types import UtcDateTime


class Attachment(SQLModel, table=True):
    __tablename__ = "attachment"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    kind: AttachmentKind
    filename: str
    sha256: str = Field(index=True)
    bytes: int
    uploaded_by: int = Field(foreign_key="user.id")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(UtcDateTime()))
