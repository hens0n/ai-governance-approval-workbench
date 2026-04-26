from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.condition import Condition, ConditionStatus
from app.models.re_review import ReReview, ReReviewTrigger
from app.models.user import User, UserRole
from app.models.use_case import UseCase, UseCaseStatus, RiskTier, Classification


def test_user_roundtrip() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            email="ao@example.gov",
            name="Alice AO",
            role=UserRole.ao,
            password_hash="x",
            active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None

        stmt = select(User).where(User.email == "ao@example.gov")
        fetched = session.exec(stmt).one()
        assert fetched.role == UserRole.ao


def test_use_case_defaults_to_draft() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        sponsor = User(email="r@example.gov", name="R", role=UserRole.requestor, password_hash="x")
        session.add(sponsor)
        session.commit()
        session.refresh(sponsor)

        uc = UseCase(
            sponsor_id=sponsor.id,
            title="Policy copilot",
            business_purpose="Answer HR questions",
            model_name="gpt-4o",
            hosting="agency-azure",
            policy_template_version="v1",
            rubric_version="v1",
        )
        session.add(uc)
        session.commit()
        session.refresh(uc)
        assert uc.status == UseCaseStatus.draft
        assert uc.risk_tier is None
        assert uc.classification is None
        assert uc.created_at.tzinfo is timezone.utc


def test_optional_datetime_fields_preserve_utc() -> None:
    """Ensure optional datetime fields (satisfied_at, completed_at) preserve UTC tzinfo."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Create a UseCase and User for foreign keys
        sponsor = User(email="r@example.gov", name="R", role=UserRole.requestor, password_hash="x")
        session.add(sponsor)
        session.commit()
        session.refresh(sponsor)

        uc = UseCase(
            sponsor_id=sponsor.id,
            title="Test",
            business_purpose="Test",
            model_name="gpt-4o",
            hosting="agency-azure",
            policy_template_version="v1",
            rubric_version="v1",
        )
        session.add(uc)
        session.commit()
        session.refresh(uc)

        # Test Condition.satisfied_at
        cond = Condition(
            use_case_id=uc.id,
            name="Test Condition",
            description="Test",
            status=ConditionStatus.proposed,
        )
        cond.satisfied_at = datetime.now(timezone.utc)
        session.add(cond)
        session.commit()
        session.refresh(cond)
        assert cond.satisfied_at is not None
        assert cond.satisfied_at.tzinfo is timezone.utc

        # Test ReReview.completed_at
        rr = ReReview(
            use_case_id=uc.id,
            due_date=datetime.now(timezone.utc),
            trigger=ReReviewTrigger.scheduled,
        )
        rr.completed_at = datetime.now(timezone.utc)
        session.add(rr)
        session.commit()
        session.refresh(rr)
        assert rr.completed_at is not None
        assert rr.completed_at.tzinfo is timezone.utc
