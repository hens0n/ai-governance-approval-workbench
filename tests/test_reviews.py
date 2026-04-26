import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Condition, ConditionStatus, Review, ReviewDecision, ReviewRole,
    UseCaseStatus, UserRole,
)
from app.services.lifecycle import LifecycleService
from app.services.sod import SoDViolation
from app.services.users import create_user


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_submitted(session: Session):
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    triager = create_user(session, email="t@x", name="T", role=UserRole.security_reviewer, password="p")
    sec = create_user(session, email="sec@x", name="Sec", role=UserRole.security_reviewer, password="p")
    priv = create_user(session, email="pri@x", name="Pri", role=UserRole.privacy_reviewer, password="p")
    ao = create_user(session, email="ao@x", name="AO", role=UserRole.ao, password="p")
    session.commit()

    uc = svc.create_draft(
        sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h",
    )
    for k, v in [
        ("contains_pii", True), ("contains_cui", False), ("external_vendor", False),
        ("hosting", "agency-azure"), ("model_kind", "llm_api"), ("data_types", ["employee_qna"]),
    ]:
        svc.upsert_intake_answer(use_case_id=uc.id, question_key=k, answer_value=v, actor_id=sponsor.id)
    svc.submit(use_case_id=uc.id, actor_id=sponsor.id)
    session.commit()
    return svc, uc, sponsor, triager, sec, priv, ao


def test_triage_then_assign_then_review() -> None:
    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.triage

    svc.assign_reviewers(
        use_case_id=uc.id, actor_id=triager.id, security_id=sec.id, privacy_id=priv.id
    )
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.in_review

    svc.submit_review(
        use_case_id=uc.id, reviewer_id=sec.id, role=ReviewRole.security,
        decision=ReviewDecision.concur, narrative="ok", conditions=[],
    )
    svc.submit_review(
        use_case_id=uc.id, reviewer_id=priv.id, role=ReviewRole.privacy,
        decision=ReviewDecision.conditional, narrative="needs pia",
        conditions=[{"name": "pia", "description": "Append PIA in 30 days"}],
    )
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.ao_decision

    conditions = session.exec(select(Condition).where(Condition.use_case_id == uc.id)).all()
    assert any(c.name == "pia" for c in conditions)


def test_triager_can_request_revision_from_triage() -> None:
    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    session.commit()

    svc.request_revision(use_case_id=uc.id, actor_id=triager.id, reason="Need DPIA reference")
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.revision_requested


def test_request_revision_requires_reason() -> None:
    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    session.commit()

    with pytest.raises(ValueError):
        svc.request_revision(use_case_id=uc.id, actor_id=triager.id, reason="   ")


def test_request_revision_blocks_sponsor() -> None:
    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    session.commit()

    with pytest.raises(SoDViolation):
        svc.request_revision(use_case_id=uc.id, actor_id=sponsor.id, reason="nope")


def test_ao_cannot_decide_if_previously_reviewed() -> None:
    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    svc.assign_reviewers(use_case_id=uc.id, actor_id=triager.id, security_id=sec.id, privacy_id=priv.id)
    svc.submit_review(
        use_case_id=uc.id, reviewer_id=sec.id, role=ReviewRole.security,
        decision=ReviewDecision.concur, narrative="ok", conditions=[],
    )
    svc.submit_review(
        use_case_id=uc.id, reviewer_id=priv.id, role=ReviewRole.privacy,
        decision=ReviewDecision.concur, narrative="ok", conditions=[],
    )
    session.commit()

    with pytest.raises(SoDViolation):
        svc.ao_decide(use_case_id=uc.id, actor_id=sec.id, decision="approve")


def test_ao_approve_sets_approved_and_schedules_re_review() -> None:
    from app.models import ReReview

    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    svc.assign_reviewers(use_case_id=uc.id, actor_id=triager.id, security_id=sec.id, privacy_id=priv.id)
    svc.submit_review(use_case_id=uc.id, reviewer_id=sec.id, role=ReviewRole.security,
                      decision=ReviewDecision.concur, narrative="ok", conditions=[])
    svc.submit_review(use_case_id=uc.id, reviewer_id=priv.id, role=ReviewRole.privacy,
                      decision=ReviewDecision.concur, narrative="ok", conditions=[])
    session.commit()

    svc.ao_decide(use_case_id=uc.id, actor_id=ao.id, decision="approve")
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.approved

    rr = session.exec(select(ReReview).where(ReReview.use_case_id == uc.id)).first()
    assert rr is not None
    assert rr.due_date > uc.updated_at


def test_ao_approve_with_conditions_freezes_accepted() -> None:
    session = _mk_session()
    svc, uc, sponsor, triager, sec, priv, ao = _seed_submitted(session)
    svc.triage(use_case_id=uc.id, actor_id=triager.id)
    svc.assign_reviewers(use_case_id=uc.id, actor_id=triager.id, security_id=sec.id, privacy_id=priv.id)
    svc.submit_review(use_case_id=uc.id, reviewer_id=sec.id, role=ReviewRole.security,
                      decision=ReviewDecision.conditional, narrative="nearly ok",
                      conditions=[{"name": "log_rag", "description": "Log RAG queries"}])
    svc.submit_review(use_case_id=uc.id, reviewer_id=priv.id, role=ReviewRole.privacy,
                      decision=ReviewDecision.concur, narrative="ok", conditions=[])
    session.commit()

    svc.ao_decide(
        use_case_id=uc.id, actor_id=ao.id, decision="approve_with_conditions",
        accepted_condition_ids="all",
    )
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.conditionally_approved

    conditions = session.exec(select(Condition).where(Condition.use_case_id == uc.id)).all()
    assert all(c.status == ConditionStatus.accepted for c in conditions)
