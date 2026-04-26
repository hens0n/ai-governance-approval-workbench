from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel

from app import config as cfg_mod
from app.main import create_app
from app.models import Attachment, AuditLogEntry, UserRole
from app.services.users import create_user


def _fresh_client(monkeypatch, tmp_path) -> TestClient:
    db = tmp_path / "t.db"
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    monkeypatch.setattr(cfg_mod.settings, "attachments_dir", tmp_path / "attachments")
    from app import db as db_mod
    new_engine = _ce(cfg_mod.settings.database_url)
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)
    with Session(new_engine) as session:
        create_user(session, email="r@x", name="R", role=UserRole.requestor, password="p")
        create_user(session, email="r2@x", name="R2", role=UserRole.requestor, password="p")
        create_user(session, email="reviewer@x", name="Rev", role=UserRole.security_reviewer, password="p")
        create_user(session, email="auditor@x", name="Aud", role=UserRole.auditor, password="p")
        session.commit()
    return TestClient(create_app())


def _login(client: TestClient) -> None:
    r = client.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303


def test_upload_persists_row_and_file(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    # First create a use case to attach to
    r = client.post(
        "/api/use-cases",
        json={
            "title": "uc1",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    content = b"hello attachment bytes"
    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("dpia.pdf", content)},
        data={"kind": "evidence"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "id" in body
    assert len(body["sha256"]) == 64
    assert body["bytes"] == len(content)

    # Verify file on disk
    sha = body["sha256"]
    expected_path = cfg_mod.settings.attachments_dir / sha[:2] / sha
    assert expected_path.exists(), f"File not found at {expected_path}"

    # Verify DB row
    from app import db as db_mod
    with Session(db_mod.engine) as session:
        row = session.get(Attachment, body["id"])
        assert row is not None
        assert row.sha256 == sha
        assert row.filename == "dpia.pdf"
        assert row.kind.value == "evidence"

        # Verify audit log
        from sqlmodel import select
        entries = session.exec(
            select(AuditLogEntry).where(AuditLogEntry.action == "upload_attachment")
        ).all()
        assert len(entries) == 1
        assert entries[0].entity_id == body["id"]


def test_download_returns_bytes(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    r = client.post(
        "/api/use-cases",
        json={
            "title": "uc1",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    content = b"download test content"
    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("report.pdf", content)},
        data={"kind": "dpia"},
    )
    assert r.status_code == 201, r.text
    attachment_id = r.json()["id"]

    r = client.get(f"/api/attachments/{attachment_id}")
    assert r.status_code == 200, r.text
    assert r.content == content
    assert "report.pdf" in r.headers["content-disposition"]


def test_duplicate_upload_dedupes_filesystem(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    r = client.post(
        "/api/use-cases",
        json={
            "title": "uc1",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    content = b"duplicate bytes"

    r1 = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("first.pdf", content)},
        data={"kind": "evidence"},
    )
    assert r1.status_code == 201
    body1 = r1.json()

    r2 = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("second.pdf", content)},
        data={"kind": "other"},
    )
    assert r2.status_code == 201
    body2 = r2.json()

    # Two distinct DB rows
    assert body1["id"] != body2["id"]
    # Same sha256
    assert body1["sha256"] == body2["sha256"]

    # Only one file on disk
    sha = body1["sha256"]
    disk_dir = cfg_mod.settings.attachments_dir / sha[:2]
    files_on_disk = list(disk_dir.iterdir())
    assert len(files_on_disk) == 1, f"Expected 1 file, found {len(files_on_disk)}"


def test_upload_requires_auth(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    # No login -- no session cookie

    r = client.post(
        "/api/use-cases/1/attachments",
        files={"file": ("dpia.pdf", b"content")},
        data={"kind": "evidence"},
    )
    assert r.status_code == 401, r.text


def test_download_content_disposition_rejects_header_injection(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    # Create a use case first so we have a valid use_case_id
    r = client.post(
        "/api/use-cases",
        json={
            "title": "injection-test-uc",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    malicious_name = 'evil";\r\nX-Injected: pwned.pdf'
    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": (malicious_name, b"payload")},
        data={"kind": "evidence"},
    )
    assert r.status_code == 201, r.text
    attachment_id = r.json()["id"]

    r = client.get(f"/api/attachments/{attachment_id}")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    # No raw CR/LF allowed in the header; no literal injected header smuggled in.
    assert "\r" not in cd and "\n" not in cd
    assert "X-Injected" not in r.headers
    # Malicious double-quote must not appear unescaped in the ASCII filename=
    assert 'filename="evil"' not in cd


# SR-06: File size cap returns 413
def test_upload_exceeds_size_limit_returns_413(monkeypatch, tmp_path) -> None:
    import app.routes.attachments as att_mod

    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    # Monkeypatch MAX_BYTES to 1 KB so the test doesn't allocate 50 MB
    monkeypatch.setattr(att_mod, "MAX_BYTES", 1024)

    r = client.post(
        "/api/use-cases",
        json={
            "title": "size-test-uc",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    oversized = b"\x00" * (1024 + 1)
    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("big.bin", oversized)},
        data={"kind": "evidence"},
    )
    assert r.status_code == 413, r.text


# SR-07: Non-sponsor requestor cannot upload to another user's use case
def test_non_sponsor_upload_returns_403(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    r = client.post(
        "/api/use-cases",
        json={
            "title": "uc-owned-by-r",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    # Log in as a different requestor
    r = client.post("/login", data={"email": "r2@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("evil.pdf", b"content")},
        data={"kind": "evidence"},
    )
    assert r.status_code == 403, r.text


# SR-07: Non-sponsor requestor cannot download an attachment on another user's use case
def test_non_sponsor_download_returns_403(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    r = client.post(
        "/api/use-cases",
        json={
            "title": "uc-owned-by-r",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("secret.pdf", b"secret content")},
        data={"kind": "evidence"},
    )
    assert r.status_code == 201
    attachment_id = r.json()["id"]

    # Log in as a different requestor
    r = client.post("/login", data={"email": "r2@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.get(f"/api/attachments/{attachment_id}")
    assert r.status_code == 403, r.text


# SR-07: A reviewer can download any attachment
def test_reviewer_can_download_any_attachment(monkeypatch, tmp_path) -> None:
    client = _fresh_client(monkeypatch, tmp_path)
    _login(client)

    r = client.post(
        "/api/use-cases",
        json={
            "title": "uc-owned-by-r",
            "business_purpose": "purpose",
            "model_name": "gpt-4o",
            "hosting": "agency-azure",
        },
    )
    assert r.status_code == 201
    uc_id = r.json()["id"]

    r = client.post(
        f"/api/use-cases/{uc_id}/attachments",
        files={"file": ("report.pdf", b"report content")},
        data={"kind": "evidence"},
    )
    assert r.status_code == 201
    attachment_id = r.json()["id"]

    # Log in as reviewer
    r = client.post("/login", data={"email": "reviewer@x", "password": "p"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.get(f"/api/attachments/{attachment_id}")
    assert r.status_code == 200, r.text
