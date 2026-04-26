import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    Review, ReviewDecision, ReviewRole, StateTransition,
    UseCase, UseCaseStatus, User, UserRole,
)
from app.services.sod import (
    SoDViolation,
    ensure_ao_clean,
    ensure_not_sponsor,
    ensure_triager_not_reviewer,
    ensure_unique_cross_cycle_roles,
)


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _mk_user(session: Session, email: str, role: UserRole) -> User:
    u = User(email=email, name=email, role=role, password_hash="x", active=True)
    session.add(u)
    session.flush()
    return u


def _mk_use_case(session: Session, sponsor_id: int) -> UseCase:
    uc = UseCase(
        sponsor_id=sponsor_id, title="t", business_purpose="p",
        model_name="m", hosting="h",
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.flush()
    return uc


def test_ensure_not_sponsor_raises_when_sponsor() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    uc = _mk_use_case(session, sponsor.id)
    with pytest.raises(SoDViolation):
        ensure_not_sponsor(session, use_case_id=uc.id, actor_id=sponsor.id)


def test_ensure_not_sponsor_ok_when_different_actor() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    other = _mk_user(session, "o@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    ensure_not_sponsor(session, use_case_id=uc.id, actor_id=other.id)


def test_ensure_unique_cross_cycle_roles_blocks_same_user_as_both() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    reviewer = _mk_user(session, "r@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    session.add(Review(
        use_case_id=uc.id, reviewer_id=reviewer.id, role=ReviewRole.security,
        decision=ReviewDecision.concur, narrative="ok",
    ))
    session.flush()
    with pytest.raises(SoDViolation):
        ensure_unique_cross_cycle_roles(
            session, use_case_id=uc.id, actor_id=reviewer.id, target_role=ReviewRole.privacy
        )


def test_ensure_triager_not_reviewer_blocks_triager_as_security() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    triager = _mk_user(session, "t@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    session.add(StateTransition(
        use_case_id=uc.id, from_state=UseCaseStatus.submitted,
        to_state=UseCaseStatus.triage, actor_id=triager.id, reason=None,
    ))
    session.flush()
    with pytest.raises(SoDViolation):
        ensure_triager_not_reviewer(
            session, use_case_id=uc.id, actor_id=triager.id, target_role=ReviewRole.security
        )


def test_ensure_ao_clean_blocks_ao_who_previously_reviewed() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    mixed = _mk_user(session, "m@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    session.add(Review(
        use_case_id=uc.id, reviewer_id=mixed.id, role=ReviewRole.security,
        decision=ReviewDecision.concur, narrative="ok",
    ))
    session.flush()
    with pytest.raises(SoDViolation):
        ensure_ao_clean(session, use_case_id=uc.id, actor_id=mixed.id)
