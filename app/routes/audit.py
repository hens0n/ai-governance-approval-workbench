from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.auth import require_role
from app.db import get_session
from app.models import AuditLogEntry, User, UserRole
from app.services.audit import verify_chain

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("/verify")
def verify(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, require_role(UserRole.auditor, UserRole.ciso, UserRole.ao)],
) -> dict:
    ok, bad_id = verify_chain(session)
    return {"ok": ok, "first_bad_id": bad_id}


@router.get("")
def list_entries(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, require_role(UserRole.auditor, UserRole.ciso, UserRole.ao)],
    entity: str | None = None,
    id: int | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.id.asc())
    if entity:
        stmt = stmt.where(AuditLogEntry.entity_type == entity)
    if id:
        stmt = stmt.where(AuditLogEntry.entity_id == id)
    rows = session.exec(stmt.limit(limit)).all()
    return [
        {
            "id": r.id,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
            "actor_id": r.actor_id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
