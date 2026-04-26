"""Service: list ReReviews due within a soft window (default 30 days).

Used by the dashboard surfaces (JSON + HTML) so reviewers can see which
post-approval re-reviews are coming due — and which have slipped past
their due date without being completed (negative ``days_remaining``).
Rows whose parent UseCase is no longer in an active approved state are
excluded; those are tracked by status counts elsewhere or are terminal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import ReReview, UseCase, UseCaseStatus

EXPIRING_THRESHOLD_DAYS = 30

_ACTIVE_APPROVED_STATUSES = (
    UseCaseStatus.approved,
    UseCaseStatus.conditionally_approved,
)


@dataclass(frozen=True)
class ExpiringRow:
    use_case_id: int
    title: str
    due_date: datetime
    days_remaining: int


def expiring_soon(
    session: Session, *, within_days: int = EXPIRING_THRESHOLD_DAYS
) -> list[ExpiringRow]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=within_days)
    stmt = (
        select(ReReview, UseCase)
        .join(UseCase, ReReview.use_case_id == UseCase.id)
        .where(
            ReReview.due_date <= cutoff,
            ReReview.completed_at.is_(None),
            UseCase.status.in_(_ACTIVE_APPROVED_STATUSES),
        )
        .order_by(ReReview.due_date.asc())
    )
    return [
        ExpiringRow(
            use_case_id=uc.id,
            title=uc.title,
            due_date=rr.due_date,
            # timedelta.days truncates toward negative infinity:
            # 4h12m → 0, -1m → -1. Callers should treat this as a
            # display approximation, not a precise countdown.
            days_remaining=(rr.due_date - now).days,
        )
        for rr, uc in session.exec(stmt).all()
    ]
