from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ControlAssignmentStatus, ControlFramework


class Control(SQLModel, table=True):
    __tablename__ = "control"

    id: Optional[int] = Field(default=None, primary_key=True)
    framework: ControlFramework
    control_id: str = Field(index=True)
    title: str
    description: str


class ControlAssignment(SQLModel, table=True):
    __tablename__ = "control_assignment"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    control_id: int = Field(foreign_key="control.id")
    status: ControlAssignmentStatus = Field(default=ControlAssignmentStatus.required)
    evidence_attachment_id: Optional[int] = Field(default=None, foreign_key="attachment.id")
