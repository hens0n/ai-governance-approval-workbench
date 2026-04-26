from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel

from app.main import create_app
from app.models import AuditLogEntry, UserRole
from app.services.users import create_user


def _fresh_client(monkeypatch, tmp_path) -> TestClient:
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    from app import db as db_mod
    new_engine = _ce(cfg_mod.settings.database_url)
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    with Session(new_engine) as session:
        create_user(session, email="r@x", name="R", role=UserRole.requestor, password="p")
        create_user(session, email="r2@x", name="R2", role=UserRole.requestor, password="p")
        create_user(session, email="ao@x", name="AO", role=UserRole.ao, password="p")
        create_user(session, email="auditor@x", name="Auditor", role=UserRole.auditor, password="p")
        session.commit()
    return TestClient(create_app())


def test_login_then_create_use_case(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.post(
        "/api/use-cases",
        json={
            "title": "copilot",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["id"] > 0


def test_unauthenticated_request_is_rejected(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    r = client.post("/api/use-cases", json={})
    assert r.status_code == 401


# SR-04: Auditor is read-only at the route layer
def test_auditor_cannot_create_use_case(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "auditor@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.post(
        "/api/use-cases",
        json={
            "title": "auditor-created",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 403, r.text


# SR-03: Non-sponsor cannot PATCH intake
def test_non_sponsor_patch_intake_returns_403(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    # Sponsor logs in and creates UC
    r = client.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post(
        "/api/use-cases",
        json={"title": "uc", "business_purpose": "p", "model_name": "m", "hosting": "h"},
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    # Different requestor (non-sponsor) logs in
    r = client.post("/login", data={"email": "r2@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.patch(f"/api/use-cases/{uc_id}/intake", json={"answers": {"foo": "bar"}})
    assert r.status_code == 403, r.text


# SR-03: Sponsor cannot PATCH intake when use case is in submitted status
def test_sponsor_patch_intake_submitted_returns_409(monkeypatch, tmp_path) -> None:
    from app import db as db_mod
    from app.models import UseCase, UseCaseStatus

    client = _fresh_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post(
        "/api/use-cases",
        json={"title": "uc", "business_purpose": "p", "model_name": "m", "hosting": "h"},
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    # Force the UC into submitted status directly
    with Session(db_mod.engine) as session:
        uc = session.get(UseCase, uc_id)
        uc.status = UseCaseStatus.submitted
        session.add(uc)
        session.commit()

    r = client.patch(f"/api/use-cases/{uc_id}/intake", json={"answers": {"foo": "bar"}})
    assert r.status_code == 409, r.text


# SR-03: Sponsor PATCH intake in draft creates audit entry with action upsert_intake_answer
def test_sponsor_patch_intake_draft_creates_audit_entry(monkeypatch, tmp_path) -> None:
    from app import db as db_mod
    from sqlmodel import select as _select

    client = _fresh_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post(
        "/api/use-cases",
        json={"title": "uc", "business_purpose": "p", "model_name": "m", "hosting": "h"},
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    r = client.patch(f"/api/use-cases/{uc_id}/intake", json={"answers": {"contains_pii": True}})
    assert r.status_code == 200, r.text

    with Session(db_mod.engine) as session:
        entries = session.exec(
            _select(AuditLogEntry).where(AuditLogEntry.action == "upsert_intake_answer")
        ).all()
        assert len(entries) == 1
        assert entries[0].entity_id == uc_id
