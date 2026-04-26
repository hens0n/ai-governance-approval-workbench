import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.auth import hash_password, login_router, require_role, verify_password
from app.db import get_session
from app.models import User, UserRole
from app.services.users import create_user
import tempfile
import os


@pytest.fixture()
def session() -> Session:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    sess = Session(engine)
    yield sess
    os.unlink(db_path)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_user_persists_hashed_password(session: Session) -> None:
    user = create_user(
        session, email="a@example.gov", name="A", role=UserRole.requestor, password="pw12345"
    )
    session.commit()
    session.refresh(user)
    assert user.password_hash != "pw12345"
    assert verify_password("pw12345", user.password_hash)


def test_login_sets_session_cookie(session: Session) -> None:
    create_user(session, email="a@example.gov", name="A", role=UserRole.requestor, password="pw")
    session.commit()

    app = FastAPI()
    app.include_router(login_router)

    def _fake_get_session():
        yield session

    app.dependency_overrides[get_session] = _fake_get_session

    client = TestClient(app)
    response = client.post(
        "/login", data={"email": "a@example.gov", "password": "pw"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "session" in response.cookies


def test_require_role_rejects_wrong_role() -> None:
    app = FastAPI()

    @app.get("/secret")
    def secret(user: User = require_role(UserRole.ao)) -> dict:  # noqa: B008
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/secret")
    assert response.status_code in (401, 403)
