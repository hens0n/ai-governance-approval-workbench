from sqlmodel import Session, SQLModel, create_engine

from app.models import UserRole
from app.services.lifecycle import LifecycleService
from app.services.packet import generate_markdown_packet
from app.services.users import create_user


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_generated_packet_contains_key_sections() -> None:
    session = _mk_session()
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()
    uc = svc.create_draft(
        sponsor_id=sponsor.id, title="Policy copilot", business_purpose="HR Q&A",
        model_name="gpt-4o", hosting="agency-azure",
    )
    for k, v in [
        ("contains_pii", True), ("contains_cui", False), ("external_vendor", False),
        ("hosting", "agency-azure"), ("model_kind", "llm_api"), ("data_types", ["employee_qna"]),
    ]:
        svc.upsert_intake_answer(use_case_id=uc.id, question_key=k, answer_value=v, actor_id=sponsor.id)
    svc.submit(use_case_id=uc.id, actor_id=sponsor.id)
    session.commit()

    packet = generate_markdown_packet(session, use_case_id=uc.id, generated_by=sponsor.id)
    md = packet.markdown
    assert "# Decision Packet" in md
    assert "Policy copilot" in md
    assert "Risk tier" in md
    assert "Controls" in md
    assert "Timeline" in md
    assert "Sponsor: " in md
