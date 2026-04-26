from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel

from app.main import create_app
from app.models import UserRole
from app.services.users import create_user


def _client(monkeypatch, tmp_path, extra_users: list[tuple[str, UserRole]] | None = None) -> TestClient:
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    from app import db as db_mod
    new_engine = _ce(cfg_mod.settings.database_url)
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    with Session(new_engine) as session:
        create_user(session, email="r@x", name="R", role=UserRole.requestor, password="p")
        for email, role in extra_users or []:
            create_user(session, email=email, name=email, role=role, password="p")
        session.commit()
    return TestClient(create_app())


def _login(c: TestClient, email: str) -> None:
    c.post("/login", data={"email": email, "password": "p"}, follow_redirects=False)


def test_login_page_renders(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path)
    r = c.get("/login")
    assert r.status_code == 200
    assert "AI Governance Workbench" in r.text


def test_dashboard_requires_auth(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path)
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 303, 401)


def test_dashboard_renders_after_login(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path)
    _login(c, "r@x")
    r = c.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text


# --- SR-23: auditor must not create use cases via UI ----------------------


def test_ui_create_use_case_blocks_auditor(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("aud@x", UserRole.auditor)])
    _login(c, "aud@x")
    r = c.post(
        "/ui/use-cases",
        data={"title": "t", "business_purpose": "b", "model_name": "m", "hosting": "h"},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_ui_create_use_case_allows_requestor(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path)
    _login(c, "r@x")
    r = c.post(
        "/ui/use-cases",
        data={"title": "t", "business_purpose": "b", "model_name": "m", "hosting": "h"},
        follow_redirects=False,
    )
    assert r.status_code == 303


# --- SR-24: writer_user defense-in-depth on UI write endpoints -----------


def test_ui_assign_reviewers_blocks_auditor(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("aud@x", UserRole.auditor)])
    _login(c, "aud@x")
    r = c.post(
        "/ui/use-cases/1/assign_reviewers",
        data={"security_id": "1", "privacy_id": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_ui_request_revision_blocks_auditor(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("aud@x", UserRole.auditor)])
    _login(c, "aud@x")
    r = c.post(
        "/ui/use-cases/1/request_revision",
        data={"reason": "anything"},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_ui_submit_review_blocks_auditor(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("aud@x", UserRole.auditor)])
    _login(c, "aud@x")
    r = c.post(
        "/ui/use-cases/1/submit_review",
        data={"decision": "concur"},
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_ui_transition_blocks_auditor(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("aud@x", UserRole.auditor)])
    _login(c, "aud@x")
    r = c.post("/ui/use-cases/1/submit", follow_redirects=False)
    assert r.status_code == 403


# --- SR-25: length caps on user-supplied free-text fields ----------------


def test_ui_request_revision_rejects_oversized_reason(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("sec@x", UserRole.security_reviewer)])
    _login(c, "sec@x")
    r = c.post(
        "/ui/use-cases/1/request_revision",
        data={"reason": "x" * 5000},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "reason" in r.text.lower()


def test_ui_submit_review_rejects_oversized_narrative(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("sec@x", UserRole.security_reviewer)])
    _login(c, "sec@x")
    r = c.post(
        "/ui/use-cases/1/submit_review",
        data={"decision": "concur", "narrative": "x" * 5000},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "narrative" in r.text.lower()


def test_ui_submit_review_rejects_too_many_conditions(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("sec@x", UserRole.security_reviewer)])
    _login(c, "sec@x")
    body = "decision=conditional&" + "&".join(
        ["condition_names=c"] * 100 + ["condition_descriptions=d"] * 100
    )
    r = c.post(
        "/ui/use-cases/1/submit_review",
        content=body.encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "conditions" in r.text.lower()


def test_ui_submit_review_rejects_oversized_condition_field(monkeypatch, tmp_path) -> None:
    c = _client(monkeypatch, tmp_path, extra_users=[("sec@x", UserRole.security_reviewer)])
    _login(c, "sec@x")
    r = c.post(
        "/ui/use-cases/1/submit_review",
        data={
            "decision": "conditional",
            "condition_names": "ok",
            "condition_descriptions": "x" * 2000,
        },
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "condition" in r.text.lower()
