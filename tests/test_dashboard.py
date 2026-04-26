from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel

from app.main import create_app
from app.models import (
    ReReview,
    ReReviewTrigger,
    UseCase,
    UseCaseStatus,
    UserRole,
)
from app.services.users import create_user


def _fresh_client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    from app import db as db_mod
    new_engine = _ce(cfg_mod.settings.database_url)
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    with Session(new_engine) as session:
        create_user(session, email="r@x", name="R", role=UserRole.requestor, password="p")
        session.commit()
    return TestClient(create_app()), new_engine


def _login(client: TestClient) -> None:
    r = client.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303


def _seed_due_rereview(engine, *, due_in_days: int, title: str = "policy copilot") -> int:
    with Session(engine) as session:
        uc = UseCase(
            title=title,
            business_purpose="bp",
            model_name="m",
            hosting="h",
            sponsor_id=1,
            status=UseCaseStatus.approved,
            policy_template_version="1.0",
            rubric_version="1.0",
        )
        session.add(uc)
        session.commit()
        session.refresh(uc)
        session.add(
            ReReview(
                use_case_id=uc.id,
                due_date=datetime.now(timezone.utc) + timedelta(days=due_in_days),
                trigger=ReReviewTrigger.scheduled,
            )
        )
        session.commit()
        return uc.id


def test_api_dashboard_requires_auth(monkeypatch, tmp_path) -> None:
    client, _ = _fresh_client(monkeypatch, tmp_path)
    r = client.get("/api/dashboard")
    assert r.status_code == 401


def test_api_dashboard_includes_empty_expiring_soon(monkeypatch, tmp_path) -> None:
    client, _ = _fresh_client(monkeypatch, tmp_path)
    _login(client)
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "expiring_soon" in body
    assert body["expiring_soon"] == {"count": 0, "items": []}


def test_api_dashboard_includes_due_rereview(monkeypatch, tmp_path) -> None:
    client, engine = _fresh_client(monkeypatch, tmp_path)
    _seed_due_rereview(engine, due_in_days=10, title="policy copilot")
    _login(client)
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["expiring_soon"]["count"] == 1
    item = body["expiring_soon"]["items"][0]
    assert item["title"] == "policy copilot"
    assert item["days_remaining"] in (9, 10)
    assert "T" in item["due_date"]
