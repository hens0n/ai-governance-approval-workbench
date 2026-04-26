import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    AuditLogEntry, IntakeAnswer, RiskTier, StateTransition, UseCase, UseCaseStatus,
    UserRole,
)
from app.services.lifecycle import LifecycleService
from app.services.sod import SoDViolation
from app.services.users import create_user


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_draft_sets_defaults() -> None:
    session = _mk_session()
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    svc = LifecycleService(session)
    uc = svc.create_draft(
        sponsor_id=sponsor.id, title="Policy copilot", business_purpose="HR Q&A",
        model_name="gpt-4o", hosting="agency-azure",
    )
    session.commit()
    assert uc.status == UseCaseStatus.draft
    assert uc.policy_template_version == "v1"
    assert uc.rubric_version == "v1"


def test_submit_scores_and_creates_transition_and_audit() -> None:
    session = _mk_session()
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    svc = LifecycleService(session)
    uc = svc.create_draft(sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h")
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="contains_pii", answer_value=True, actor_id=sponsor.id)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="contains_cui", answer_value=False, actor_id=sponsor.id)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="external_vendor", answer_value=False, actor_id=sponsor.id)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="hosting", answer_value="agency-azure", actor_id=sponsor.id)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="model_kind", answer_value="llm_api", actor_id=sponsor.id)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="data_types", answer_value=["employee_qna"], actor_id=sponsor.id)

    svc.submit(use_case_id=uc.id, actor_id=sponsor.id)
    session.commit()
    session.refresh(uc)

    assert uc.status == UseCaseStatus.submitted
    assert uc.risk_tier == RiskTier.moderate
    transitions = session.exec(select(StateTransition).where(StateTransition.use_case_id == uc.id)).all()
    assert any(t.to_state == UseCaseStatus.submitted for t in transitions)
    audit = session.exec(select(AuditLogEntry).where(AuditLogEntry.entity_id == uc.id)).all()
    assert any(e.action == "submit" for e in audit)


def test_submit_by_non_sponsor_fails_sod() -> None:
    session = _mk_session()
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    other = create_user(session, email="o@x", name="O", role=UserRole.requestor, password="p")
    session.commit()

    svc = LifecycleService(session)
    uc = svc.create_draft(sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h")
    session.commit()

    with pytest.raises(SoDViolation):
        svc.submit(use_case_id=uc.id, actor_id=other.id)


def test_intake_answer_versioning_is_monotonic() -> None:
    session = _mk_session()
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    svc = LifecycleService(session)
    uc = svc.create_draft(sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h")
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="data_types", answer_value=["a"], actor_id=sponsor.id)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="data_types", answer_value=["a", "b"], actor_id=sponsor.id)
    session.commit()

    versions = session.exec(
        select(IntakeAnswer).where(IntakeAnswer.use_case_id == uc.id, IntakeAnswer.question_key == "data_types")
    ).all()
    assert {v.version for v in versions} == {1, 2}
