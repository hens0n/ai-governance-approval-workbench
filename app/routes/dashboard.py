from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.models import UseCase, User
from app.services.expiring import expiring_soon

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

    expiring_rows = expiring_soon(session)
    return {
        "total": len(rows),
        "by_status": by_status,
        "by_tier": by_tier,
        "expiring_soon": {
            "count": len(expiring_rows),
            "items": [
                {
                    "use_case_id": r.use_case_id,
                    "title": r.title,
                    "due_date": r.due_date.isoformat(),
                    "days_remaining": r.days_remaining,
                }
                for r in expiring_rows
            ],
        },
    }
