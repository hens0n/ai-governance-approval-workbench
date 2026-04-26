from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.models import (
    ReReview,
    ReReviewTrigger,
    UseCase,
    UseCaseStatus,
    User,
    UserRole,
)
from app.services.expiring import EXPIRING_THRESHOLD_DAYS, ExpiringRow, expiring_soon


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(email="r@x", name="R", role=UserRole.requestor, password_hash="x"))
        s.commit()
        yield s


def _make_uc(session: Session, *, status: UseCaseStatus, title: str = "uc") -> UseCase:
    uc = UseCase(
        title=title,
        business_purpose="bp",
        model_name="m",
        hosting="h",
        sponsor_id=1,
        status=status,
        policy_template_version="1.0",
        rubric_version="1.0",
    )
    session.add(uc)
    session.commit()
    session.refresh(uc)
    return uc


def _make_rereview(
    session: Session, *, use_case_id: int, due_in_days: int, completed: bool = False
) -> ReReview:
    due = datetime.now(timezone.utc) + timedelta(days=due_in_days)
    rr = ReReview(
        use_case_id=use_case_id,
        due_date=due,
        trigger=ReReviewTrigger.scheduled,
        completed_at=datetime.now(timezone.utc) if completed else None,
    )
    session.add(rr)
    session.commit()
    session.refresh(rr)
    return rr


def test_default_threshold_constant():
    assert EXPIRING_THRESHOLD_DAYS == 30


def test_empty_db_returns_empty_list(session):
    assert expiring_soon(session) == []


def test_due_in_5_days_with_approved_parent_is_included(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=5)
    rows = expiring_soon(session)
    assert len(rows) == 1
    assert rows[0].use_case_id == uc.id
    assert rows[0].title == "uc"
    assert rows[0].days_remaining in (4, 5)


def test_due_in_60_days_is_excluded(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=60)
    assert expiring_soon(session) == []


def test_re_review_required_parent_is_excluded(session):
    uc = _make_uc(session, status=UseCaseStatus.re_review_required)
    _make_rereview(session, use_case_id=uc.id, due_in_days=5)
    assert expiring_soon(session) == []


def test_terminal_status_parents_are_excluded(session):
    for status in (UseCaseStatus.revoked, UseCaseStatus.rejected, UseCaseStatus.withdrawn):
        uc = _make_uc(session, status=status, title=f"uc-{status.value}")
        _make_rereview(session, use_case_id=uc.id, due_in_days=5)
    assert expiring_soon(session) == []


def test_completed_rereview_is_excluded(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=5, completed=True)
    assert expiring_soon(session) == []


def test_results_ordered_by_due_date_ascending(session):
    uc1 = _make_uc(session, status=UseCaseStatus.approved, title="later")
    _make_rereview(session, use_case_id=uc1.id, due_in_days=20)
    uc2 = _make_uc(session, status=UseCaseStatus.conditionally_approved, title="sooner")
    _make_rereview(session, use_case_id=uc2.id, due_in_days=3)
    rows = expiring_soon(session)
    assert [r.title for r in rows] == ["sooner", "later"]


def test_custom_threshold_honored(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=10)
    assert expiring_soon(session, within_days=7) == []
    assert len(expiring_soon(session, within_days=14)) == 1


def test_past_due_row_has_negative_days_remaining(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=-3)
    rows = expiring_soon(session)
    assert len(rows) == 1
    assert rows[0].days_remaining in (-4, -3)
