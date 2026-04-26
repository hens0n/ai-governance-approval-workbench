import pytest
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Classification, ReReview, RiskTier, UseCase, UseCaseStatus, UserRole,
)
from app.services.lifecycle import LifecycleService
from app.services.sod import SoDViolation
from app.services.users import create_user


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_check_expirations_moves_overdue_to_re_review_required() -> None:
    session = _mk_session()
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    uc = UseCase(
        sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h",
        status=UseCaseStatus.approved, risk_tier=RiskTier.low, classification=Classification.internal,
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.flush()
    session.add(
        ReReview(
            use_case_id=uc.id,
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    session.commit()

    moved = svc.check_expirations(actor_id=sponsor.id)
    session.commit()
    assert uc.id in moved
    session.refresh(uc)
    assert uc.status == UseCaseStatus.re_review_required


def test_material_change_non_sponsor_non_ao_raises_sod() -> None:
    """SR-01: A non-sponsor requestor must not be able to trigger a material change."""
    session = _mk_session()
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    other = create_user(session, email="o@x", name="O", role=UserRole.requestor, password="p")
    session.commit()

    uc = UseCase(
        sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h",
        status=UseCaseStatus.approved, risk_tier=RiskTier.low, classification=Classification.internal,
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.commit()

    with pytest.raises(SoDViolation, match="only the sponsor, AO, or CISO"):
        svc.trigger_material_change(use_case_id=uc.id, actor_id=other.id, reason="hack")


def test_material_change_forces_re_review() -> None:
    session = _mk_session()
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    uc = UseCase(
        sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h",
        status=UseCaseStatus.approved, risk_tier=RiskTier.low, classification=Classification.internal,
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.commit()

    svc.trigger_material_change(use_case_id=uc.id, actor_id=sponsor.id, reason="model swap")
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.re_review_required
    rr = session.exec(select(ReReview).where(ReReview.use_case_id == uc.id)).first()
    assert rr is not None
    assert rr.trigger.value == "material_change"
