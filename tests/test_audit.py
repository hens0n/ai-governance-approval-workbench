import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import AuditLogEntry, UserRole
from app.services.audit import GENESIS_HASH, AuditLogWriter, verify_chain
from app.services.users import create_user


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_first_entry_uses_genesis_prev_hash() -> None:
    session = _mk_session()
    writer = AuditLogWriter(session)
    entry = writer.append(
        actor_id=1, action="create", entity_type="use_case", entity_id=42, payload={"k": "v"}
    )
    session.commit()
    assert entry.prev_hash == GENESIS_HASH
    assert entry.hash != GENESIS_HASH


def test_chain_links_entries() -> None:
    session = _mk_session()
    writer = AuditLogWriter(session)
    a = writer.append(actor_id=1, action="a", entity_type="x", entity_id=1, payload={})
    b = writer.append(actor_id=1, action="b", entity_type="x", entity_id=1, payload={})
    session.commit()
    assert b.prev_hash == a.hash


def test_verify_chain_detects_tamper() -> None:
    session = _mk_session()
    writer = AuditLogWriter(session)
    writer.append(actor_id=1, action="a", entity_type="x", entity_id=1, payload={})
    writer.append(actor_id=1, action="b", entity_type="x", entity_id=1, payload={})
    session.commit()

    ok, bad_id = verify_chain(session)
    assert ok is True
    assert bad_id is None

    middle = session.get(AuditLogEntry, 1)
    middle.payload = {"tampered": True}
    session.add(middle)
    session.commit()

    ok, bad_id = verify_chain(session)
    assert ok is False
    assert bad_id == 1


def test_canonical_json_is_stable() -> None:
    from app.services.audit import _canonical_json

    a = _canonical_json({"b": 1, "a": [2, 1]})
    b = _canonical_json({"a": [2, 1], "b": 1})
    assert a == b
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


# --- Route-level tests for SR-08 and SR-10 ---

def _fresh_audit_client(monkeypatch, tmp_path) -> TestClient:
    from app import config as cfg_mod
    from app import db as db_mod
    from app.main import create_app

    db = tmp_path / "t.db"
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    new_engine = _ce(cfg_mod.settings.database_url)
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    with Session(new_engine) as session:
        create_user(session, email="requestor@x", name="Req", role=UserRole.requestor, password="p")
        create_user(session, email="auditor@x", name="Aud", role=UserRole.auditor, password="p")
        session.commit()
    return TestClient(create_app())


# SR-08: Requestor gets 403 on GET /api/audit-log
def test_requestor_cannot_read_audit_log(monkeypatch, tmp_path) -> None:
    client = _fresh_audit_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "requestor@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.get("/api/audit-log")
    assert r.status_code == 403, r.text


# SR-08: Auditor can read the audit log
def test_auditor_can_read_audit_log(monkeypatch, tmp_path) -> None:
    client = _fresh_audit_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "auditor@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.get("/api/audit-log")
    assert r.status_code == 200, r.text


# SR-10: limit=10000 exceeds server-side cap and returns 422
def test_audit_log_limit_too_large_returns_422(monkeypatch, tmp_path) -> None:
    client = _fresh_audit_client(monkeypatch, tmp_path)
    r = client.post("/login", data={"email": "auditor@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.get("/api/audit-log?limit=10000")
    assert r.status_code == 422, r.text
