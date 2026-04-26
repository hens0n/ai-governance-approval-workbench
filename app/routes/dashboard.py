from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.models import UseCase, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def summary(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict:
    rows = session.exec(select(UseCase)).all()
    by_status: dict[str, int] = {}
    for uc in rows:
        by_status[uc.status.value] = by_status.get(uc.status.value, 0) + 1
    by_tier: dict[str, int] = {}
    for uc in rows:
        key = uc.risk_tier.value if uc.risk_tier else "unscored"
        by_tier[key] = by_tier.get(key, 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_tier": by_tier}
