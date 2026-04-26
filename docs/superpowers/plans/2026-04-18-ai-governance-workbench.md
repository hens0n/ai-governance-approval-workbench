# AI Governance Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a v1 AI Governance Review and Approval Workbench: a FastAPI + HTMX web app that takes a proposed AI use case through intake, risk scoring, parallel privacy/security reviews, AO decision, conditions, re-review scheduling, and an exportable Markdown decision packet — with a hash-chained audit log and SoD enforced in the service layer.

**Architecture:** Single-container Python app. FastAPI for HTTP, SQLModel over SQLite for persistence, Jinja + HTMX + Tailwind (CDN) for UI, hand-rolled state machine in one file, hash-chained audit log in the same DB, pluggable LLM seam off by default. Companion spec: `docs/superpowers/specs/2026-04-17-ai-governance-workbench-design.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, SQLAlchemy, Alembic, pytest, passlib[argon2], itsdangerous, Jinja2, HTMX (CDN), Tailwind (CDN), WeasyPrint (optional), Docker.

---

## Task 0: Bootstrap Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`
- Create: `Makefile`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "ai-governance-workbench"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlmodel>=0.0.22",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "pydantic>=2.7",
  "pydantic-settings>=2.4",
  "passlib[argon2]>=1.7",
  "itsdangerous>=2.2",
  "python-multipart>=0.0.9",
  "jinja2>=3.1",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "ruff>=0.5",
  "mypy>=1.10",
]
pdf = ["weasyprint>=62.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Create `.python-version` and `.gitignore`**

`.python-version`:
```
3.12
```

`.gitignore`:
```
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
data/
attachments/
*.db
*.db-wal
*.db-shm
secrets/
.coverage
```

- [ ] **Step 3: Create `app/config.py`**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/workbench.db"
    attachments_dir: Path = Path("./data/attachments")
    session_secret: str = "dev-only-change-me"
    ai_features_enabled: bool = False
    environment: str = "dev"


settings = Settings()
```

- [ ] **Step 4: Create minimal FastAPI app in `app/main.py`**

```python
from fastapi import FastAPI

from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI Governance Workbench", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.environment}

    return app


app = create_app()
```

- [ ] **Step 5: Create `tests/conftest.py` with a client fixture**

```python
from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())
```

- [ ] **Step 6: Write smoke test in `tests/test_smoke.py`**

```python
from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
```

- [ ] **Step 7: Create `Makefile`**

```makefile
.PHONY: install test run demo reset

install:
	python -m pip install -e '.[dev]'

test:
	pytest

run:
	uvicorn app.main:app --reload --port 8000

demo:
	docker compose -f docker/compose.yml up --build

reset:
	rm -rf data
	mkdir -p data/attachments
```

- [ ] **Step 8: Run tests**

Run: `pytest -v`
Expected: `tests/test_smoke.py::test_healthz_returns_ok PASSED`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .python-version .gitignore app tests Makefile
git commit -m "chore: bootstrap FastAPI skeleton with healthz smoke test"
```

---

## Task 1: Core Models and Database Bootstrapping

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/enums.py`
- Create: `app/models/user.py`
- Create: `app/models/use_case.py`
- Create: `app/models/intake.py`
- Create: `app/models/attachment.py`
- Create: `app/models/review.py`
- Create: `app/models/condition.py`
- Create: `app/models/state_transition.py`
- Create: `app/models/control.py`
- Create: `app/models/re_review.py`
- Create: `app/models/review_packet.py`
- Create: `app/models/audit.py`
- Create: `app/db.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test for model creation in `tests/test_models.py`**

```python
from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, create_engine, select

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: ImportError — modules don't exist yet.

- [ ] **Step 3: Create `app/models/enums.py`**

```python
from enum import Enum


class UserRole(str, Enum):
    requestor = "requestor"
    security_reviewer = "security_reviewer"
    privacy_reviewer = "privacy_reviewer"
    ao = "ao"
    ciso = "ciso"
    auditor = "auditor"


class UseCaseStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    triage = "triage"
    revision_requested = "revision_requested"
    in_review = "in_review"
    ao_decision = "ao_decision"
    approved = "approved"
    conditionally_approved = "conditionally_approved"
    rejected = "rejected"
    re_review_required = "re_review_required"
    revoked = "revoked"
    withdrawn = "withdrawn"


class RiskTier(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class Classification(str, Enum):
    public = "public"
    internal = "internal"
    sensitive = "sensitive"
    cui = "cui"


class ReviewRole(str, Enum):
    security = "security"
    privacy = "privacy"


class ReviewDecision(str, Enum):
    concur = "concur"
    non_concur = "non_concur"
    conditional = "conditional"


class ConditionStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    satisfied = "satisfied"
    waived = "waived"


class AttachmentKind(str, Enum):
    architecture = "architecture"
    dpia = "dpia"
    vendor_contract = "vendor_contract"
    model_card = "model_card"
    evidence = "evidence"
    other = "other"


class ControlFramework(str, Enum):
    nist_ai_rmf = "nist_ai_rmf"
    nist_800_53 = "nist_800_53"


class ControlAssignmentStatus(str, Enum):
    required = "required"
    evidenced = "evidenced"
    waived = "waived"


class ReReviewTrigger(str, Enum):
    scheduled = "scheduled"
    material_change = "material_change"
    policy_change = "policy_change"
```

- [ ] **Step 4: Create `app/models/user.py`**

```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import UserRole


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    role: UserRole
    password_hash: str
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 5: Create `app/models/use_case.py`**

```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import Classification, RiskTier, UseCaseStatus


class UseCase(SQLModel, table=True):
    __tablename__ = "use_case"

    id: Optional[int] = Field(default=None, primary_key=True)
    sponsor_id: int = Field(foreign_key="user.id", index=True)
    title: str
    business_purpose: str
    model_name: str
    hosting: str
    status: UseCaseStatus = Field(default=UseCaseStatus.draft, index=True)
    risk_tier: Optional[RiskTier] = None
    classification: Optional[Classification] = None
    policy_template_version: str
    rubric_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 6: Create remaining model files**

`app/models/intake.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class IntakeAnswer(SQLModel, table=True):
    __tablename__ = "intake_answer"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    question_key: str = Field(index=True)
    answer_value: dict = Field(sa_column=Column(JSON))
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`app/models/attachment.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import AttachmentKind


class Attachment(SQLModel, table=True):
    __tablename__ = "attachment"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    kind: AttachmentKind
    filename: str
    sha256: str = Field(index=True)
    bytes: int
    uploaded_by: int = Field(foreign_key="user.id")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`app/models/review.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ReviewDecision, ReviewRole


class Review(SQLModel, table=True):
    __tablename__ = "review"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    reviewer_id: int = Field(foreign_key="user.id")
    role: ReviewRole
    decision: ReviewDecision
    narrative: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`app/models/condition.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ConditionStatus


class Condition(SQLModel, table=True):
    __tablename__ = "condition"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    name: str
    description: str
    status: ConditionStatus = Field(default=ConditionStatus.proposed)
    source_review_id: Optional[int] = Field(default=None, foreign_key="review.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    satisfied_at: Optional[datetime] = None
```

`app/models/state_transition.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import UseCaseStatus


class StateTransition(SQLModel, table=True):
    __tablename__ = "state_transition"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    from_state: UseCaseStatus
    to_state: UseCaseStatus
    actor_id: int = Field(foreign_key="user.id")
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`app/models/control.py`:
```python
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ControlAssignmentStatus, ControlFramework


class Control(SQLModel, table=True):
    __tablename__ = "control"

    id: Optional[int] = Field(default=None, primary_key=True)
    framework: ControlFramework
    control_id: str = Field(index=True)
    title: str
    description: str


class ControlAssignment(SQLModel, table=True):
    __tablename__ = "control_assignment"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    control_id: int = Field(foreign_key="control.id")
    status: ControlAssignmentStatus = Field(default=ControlAssignmentStatus.required)
    evidence_attachment_id: Optional[int] = Field(default=None, foreign_key="attachment.id")
```

`app/models/re_review.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ReReviewTrigger


class ReReview(SQLModel, table=True):
    __tablename__ = "re_review"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    due_date: datetime
    trigger: ReReviewTrigger = Field(default=ReReviewTrigger.scheduled)
    completed_at: Optional[datetime] = None
    status: str = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`app/models/review_packet.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class ReviewPacket(SQLModel, table=True):
    __tablename__ = "review_packet"

    id: Optional[int] = Field(default=None, primary_key=True)
    use_case_id: int = Field(foreign_key="use_case.id", index=True)
    version: int
    markdown: str
    pdf_path: Optional[str] = None
    generated_by: int = Field(foreign_key="user.id")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`app/models/audit.py`:
```python
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class AuditLogEntry(SQLModel, table=True):
    __tablename__ = "audit_log_entry"

    id: Optional[int] = Field(default=None, primary_key=True)
    prev_hash: str
    hash: str = Field(index=True)
    actor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    action: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_id: int = Field(index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 7: Create `app/models/__init__.py`** — re-export everything so `SQLModel.metadata` sees all tables

```python
from app.models.attachment import Attachment
from app.models.audit import AuditLogEntry
from app.models.condition import Condition
from app.models.control import Control, ControlAssignment
from app.models.enums import (
    AttachmentKind,
    Classification,
    ConditionStatus,
    ControlAssignmentStatus,
    ControlFramework,
    ReReviewTrigger,
    ReviewDecision,
    ReviewRole,
    RiskTier,
    UseCaseStatus,
    UserRole,
)
from app.models.intake import IntakeAnswer
from app.models.re_review import ReReview
from app.models.review import Review
from app.models.review_packet import ReviewPacket
from app.models.state_transition import StateTransition
from app.models.use_case import UseCase
from app.models.user import User

__all__ = [
    "Attachment", "AuditLogEntry", "Condition", "Control", "ControlAssignment",
    "AttachmentKind", "Classification", "ConditionStatus", "ControlAssignmentStatus",
    "ControlFramework", "ReReviewTrigger", "ReviewDecision", "ReviewRole", "RiskTier",
    "UseCaseStatus", "UserRole", "IntakeAnswer", "ReReview", "Review", "ReviewPacket",
    "StateTransition", "UseCase", "User",
]
```

- [ ] **Step 8: Create `app/db.py`** (engine + session helpers)

```python
from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _conn_record) -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    import app.models  # ensure tables registered  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
```

- [ ] **Step 9: Re-run model tests**

Run: `pytest tests/test_models.py -v`
Expected: both tests PASS.

- [ ] **Step 10: Commit**

```bash
git add app/models app/db.py tests/test_models.py
git commit -m "feat: add SQLModel schema for workbench entities"
```

---

## Task 2: Hash-Chained Audit Log Service

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write failing test in `tests/test_audit.py`**

```python
import hashlib

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import AuditLogEntry
from app.services.audit import GENESIS_HASH, AuditLogWriter, verify_chain


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audit.py -v`
Expected: ImportError — `app.services.audit` doesn't exist.

- [ ] **Step 3: Create `app/services/__init__.py`** (empty file)

```python
```

- [ ] **Step 4: Create `app/services/audit.py`**

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from app.models import AuditLogEntry

GENESIS_HASH = "0" * 64


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _compute_hash(prev_hash: str, entry_payload: dict) -> str:
    material = prev_hash.encode("utf-8") + b"|" + _canonical_json(entry_payload)
    return hashlib.sha256(material).hexdigest()


class AuditLogWriter:
    """Appends hash-chained entries. Callers own the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _latest_hash(self) -> str:
        stmt = select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(1)
        latest = self._session.exec(stmt).first()
        return latest.hash if latest else GENESIS_HASH

    def append(
        self,
        *,
        actor_id: Optional[int],
        action: str,
        entity_type: str,
        entity_id: int,
        payload: dict,
    ) -> AuditLogEntry:
        prev_hash = self._latest_hash()
        created_at = datetime.now(timezone.utc)
        hash_input = {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "created_at": created_at.isoformat(),
        }
        entry = AuditLogEntry(
            prev_hash=prev_hash,
            hash=_compute_hash(prev_hash, hash_input),
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            created_at=created_at,
        )
        self._session.add(entry)
        self._session.flush()
        return entry


def verify_chain(session: Session) -> tuple[bool, Optional[int]]:
    """Walk the log in order; return (ok, first_bad_id)."""
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.id.asc())
    entries = session.exec(stmt).all()
    prev_hash = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != prev_hash:
            return False, entry.id
        hash_input = {
            "actor_id": entry.actor_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "payload": entry.payload,
            "created_at": entry.created_at.isoformat(),
        }
        expected = _compute_hash(entry.prev_hash, hash_input)
        if expected != entry.hash:
            return False, entry.id
        prev_hash = entry.hash
    return True, None
```

- [ ] **Step 5: Run audit tests**

Run: `pytest tests/test_audit.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/__init__.py app/services/audit.py tests/test_audit.py
git commit -m "feat: add hash-chained audit log writer and verifier"
```

---

## Task 3: Auth — Password Hashing, Sessions, Role Middleware

**Files:**
- Create: `app/auth.py`
- Create: `app/services/users.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write failing tests in `tests/test_auth.py`**

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.auth import hash_password, login_router, require_role, verify_password
from app.models import User, UserRole
from app.services.users import create_user


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


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


def test_login_sets_session_cookie(session: Session, monkeypatch) -> None:
    create_user(session, email="a@example.gov", name="A", role=UserRole.requestor, password="pw")
    session.commit()

    app = FastAPI()
    app.include_router(login_router)

    from app import auth as auth_mod

    def _fake_get_session():
        yield session

    monkeypatch.setattr(auth_mod, "get_session", _fake_get_session)

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `app/services/users.py`**

```python
from sqlmodel import Session, select

from app.models import User, UserRole


def create_user(
    session: Session, *, email: str, name: str, role: UserRole, password: str
) -> User:
    from app.auth import hash_password  # avoid import cycle at module load

    user = User(
        email=email,
        name=name,
        role=role,
        password_hash=hash_password(password),
        active=True,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()
```

- [ ] **Step 4: Create `app/auth.py`**

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.models import User, UserRole
from app.services.users import get_user_by_email

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")
_serializer = URLSafeSerializer(settings.session_secret, salt="session")

login_router = APIRouter()


def hash_password(plaintext: str) -> str:
    return _pwd.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    return _pwd.verify(plaintext, hashed)


def _make_cookie(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def _read_cookie(token: str) -> int | None:
    try:
        data = _serializer.loads(token)
    except BadSignature:
        return None
    return data.get("uid")


def current_user(
    session: Annotated[Session, Depends(get_session)],
    session_token: Annotated[str | None, Cookie(alias="session")] = None,
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not signed in")
    uid = _read_cookie(session_token)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    user = session.get(User, uid)
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive user")
    return user


def require_role(*roles: UserRole):
    def _guard(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="role not permitted")
        return user

    return Depends(_guard)


@login_router.post("/login")
def login(
    session: Annotated[Session, Depends(get_session)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = get_user_by_email(session, email)
    if not user or not user.active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        "session", _make_cookie(user.id), httponly=True, samesite="lax", secure=False
    )
    return response


@login_router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
```

- [ ] **Step 5: Run auth tests**

Run: `pytest tests/test_auth.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/auth.py app/services/users.py tests/test_auth.py
git commit -m "feat: add Argon2 password hashing, session cookie, role guard"
```

---

## Task 4: Separation of Duties Service

**Files:**
- Create: `app/services/sod.py`
- Test: `tests/test_sod.py`

- [ ] **Step 1: Write failing test in `tests/test_sod.py`**

```python
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    Review, ReviewDecision, ReviewRole, StateTransition,
    UseCase, UseCaseStatus, User, UserRole,
)
from app.services.sod import (
    SoDViolation,
    ensure_ao_clean,
    ensure_not_sponsor,
    ensure_triager_not_reviewer,
    ensure_unique_cross_cycle_roles,
)


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _mk_user(session: Session, email: str, role: UserRole) -> User:
    u = User(email=email, name=email, role=role, password_hash="x", active=True)
    session.add(u)
    session.flush()
    return u


def _mk_use_case(session: Session, sponsor_id: int) -> UseCase:
    uc = UseCase(
        sponsor_id=sponsor_id, title="t", business_purpose="p",
        model_name="m", hosting="h",
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.flush()
    return uc


def test_ensure_not_sponsor_raises_when_sponsor() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    uc = _mk_use_case(session, sponsor.id)
    with pytest.raises(SoDViolation):
        ensure_not_sponsor(session, use_case_id=uc.id, actor_id=sponsor.id)


def test_ensure_not_sponsor_ok_when_different_actor() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    other = _mk_user(session, "o@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    ensure_not_sponsor(session, use_case_id=uc.id, actor_id=other.id)


def test_ensure_unique_cross_cycle_roles_blocks_same_user_as_both() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    reviewer = _mk_user(session, "r@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    session.add(Review(
        use_case_id=uc.id, reviewer_id=reviewer.id, role=ReviewRole.security,
        decision=ReviewDecision.concur, narrative="ok",
    ))
    session.flush()
    with pytest.raises(SoDViolation):
        ensure_unique_cross_cycle_roles(
            session, use_case_id=uc.id, actor_id=reviewer.id, target_role=ReviewRole.privacy
        )


def test_ensure_triager_not_reviewer_blocks_triager_as_security() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    triager = _mk_user(session, "t@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    session.add(StateTransition(
        use_case_id=uc.id, from_state=UseCaseStatus.submitted,
        to_state=UseCaseStatus.triage, actor_id=triager.id, reason=None,
    ))
    session.flush()
    with pytest.raises(SoDViolation):
        ensure_triager_not_reviewer(
            session, use_case_id=uc.id, actor_id=triager.id, target_role=ReviewRole.security
        )


def test_ensure_ao_clean_blocks_ao_who_previously_reviewed() -> None:
    session = _mk_session()
    sponsor = _mk_user(session, "s@x", UserRole.requestor)
    mixed = _mk_user(session, "m@x", UserRole.security_reviewer)
    uc = _mk_use_case(session, sponsor.id)
    session.add(Review(
        use_case_id=uc.id, reviewer_id=mixed.id, role=ReviewRole.security,
        decision=ReviewDecision.concur, narrative="ok",
    ))
    session.flush()
    with pytest.raises(SoDViolation):
        ensure_ao_clean(session, use_case_id=uc.id, actor_id=mixed.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sod.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `app/services/sod.py`**

```python
from __future__ import annotations

from sqlmodel import Session, select

from app.models import Review, ReviewRole, StateTransition, UseCase, UseCaseStatus


class SoDViolation(Exception):
    """Raised when a separation-of-duties invariant would be breached."""


def ensure_not_sponsor(session: Session, *, use_case_id: int, actor_id: int) -> None:
    uc = session.get(UseCase, use_case_id)
    if uc is None:
        raise SoDViolation(f"use case {use_case_id} not found")
    if uc.sponsor_id == actor_id:
        raise SoDViolation("sponsor cannot act as reviewer or AO on their own case")


def ensure_unique_cross_cycle_roles(
    session: Session, *, use_case_id: int, actor_id: int, target_role: ReviewRole
) -> None:
    other_role = ReviewRole.privacy if target_role == ReviewRole.security else ReviewRole.security
    stmt = select(Review).where(
        Review.use_case_id == use_case_id,
        Review.reviewer_id == actor_id,
        Review.role == other_role,
    )
    if session.exec(stmt).first() is not None:
        raise SoDViolation(
            f"actor previously served as {other_role.value} reviewer on this case"
        )


def ensure_triager_not_reviewer(
    session: Session, *, use_case_id: int, actor_id: int, target_role: ReviewRole
) -> None:
    if target_role != ReviewRole.security:
        return
    stmt = select(StateTransition).where(
        StateTransition.use_case_id == use_case_id,
        StateTransition.to_state == UseCaseStatus.triage,
        StateTransition.actor_id == actor_id,
    )
    if session.exec(stmt).first() is not None:
        raise SoDViolation("triager cannot also be the assigned Security reviewer on this case")


def ensure_ao_clean(session: Session, *, use_case_id: int, actor_id: int) -> None:
    reviewed = session.exec(
        select(Review).where(Review.use_case_id == use_case_id, Review.reviewer_id == actor_id)
    ).first()
    if reviewed is not None:
        raise SoDViolation("AO cannot have served as a reviewer on this case")

    triaged = session.exec(
        select(StateTransition).where(
            StateTransition.use_case_id == use_case_id,
            StateTransition.to_state == UseCaseStatus.triage,
            StateTransition.actor_id == actor_id,
        )
    ).first()
    if triaged is not None:
        raise SoDViolation("AO cannot have served as triager on this case")
```

- [ ] **Step 4: Run SoD tests**

Run: `pytest tests/test_sod.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/sod.py tests/test_sod.py
git commit -m "feat: add SoD enforcement service with invariants"
```

---

## Task 5: Risk Scoring and Control Recommendation Engines

**Files:**
- Create: `app/policy/__init__.py`
- Create: `app/policy/rubric.json`
- Create: `app/policy/template.json`
- Create: `app/services/scoring.py`
- Create: `app/services/controls.py`
- Test: `tests/test_scoring.py`
- Test: `tests/test_controls.py`

- [ ] **Step 1: Write failing test in `tests/test_scoring.py`**

```python
from app.models import Classification, RiskTier
from app.services.scoring import score_use_case


def test_low_tier_internal_no_pii() -> None:
    answers = {
        "data_types": ["internal_policy_docs"],
        "contains_pii": False,
        "contains_cui": False,
        "hosting": "agency-azure",
        "model_kind": "llm_api",
        "external_vendor": False,
    }
    result = score_use_case(answers)
    assert result.tier == RiskTier.low
    assert result.classification == Classification.internal
    assert result.rubric_version == "v1"


def test_high_tier_on_cui_plus_external_vendor() -> None:
    answers = {
        "data_types": ["contract_terms", "vendor_identities"],
        "contains_pii": False,
        "contains_cui": True,
        "hosting": "vendor_cloud",
        "model_kind": "llm_api",
        "external_vendor": True,
    }
    result = score_use_case(answers)
    assert result.tier == RiskTier.high
    assert result.classification == Classification.cui


def test_moderate_tier_on_pii_internal() -> None:
    answers = {
        "data_types": ["employee_qna"],
        "contains_pii": True,
        "contains_cui": False,
        "hosting": "agency-azure",
        "model_kind": "llm_api",
        "external_vendor": False,
    }
    result = score_use_case(answers)
    assert result.tier == RiskTier.moderate
    assert result.classification == Classification.sensitive


def test_result_includes_breakdown_for_auditability() -> None:
    answers = {
        "data_types": [],
        "contains_pii": False,
        "contains_cui": True,
        "hosting": "agency-azure",
        "model_kind": "ml_model",
        "external_vendor": False,
    }
    result = score_use_case(answers)
    assert any("cui" in factor.lower() for factor in result.breakdown)
```

- [ ] **Step 2: Create `app/policy/rubric.json`**

```json
{
  "version": "v1",
  "rules": [
    {"id": "cui", "when": {"contains_cui": true}, "tier_min": "high", "classification": "cui"},
    {"id": "external_vendor", "when": {"external_vendor": true}, "tier_min": "high"},
    {"id": "pii", "when": {"contains_pii": true}, "tier_min": "moderate", "classification": "sensitive"},
    {"id": "internal_only", "when": {"contains_pii": false, "contains_cui": false, "external_vendor": false}, "tier_min": "low", "classification": "internal"}
  ]
}
```

- [ ] **Step 3: Create `app/policy/template.json`**

```json
{
  "version": "v1",
  "base_controls": {
    "low": ["AC-2", "AU-2", "RA-3"],
    "moderate": ["AC-2", "AC-5", "AU-2", "AU-9", "RA-3", "CM-3"],
    "high": ["AC-2", "AC-5", "AC-6", "AU-2", "AU-9", "RA-3", "CM-3", "SI-12"]
  },
  "additional": {
    "external_vendor": ["CA-3", "SA-9", "SR-3"],
    "contains_cui": ["SC-8", "SC-28"],
    "model_kind_ml_model": ["SI-7"]
  },
  "ai_rmf": {
    "low": ["Govern", "Map"],
    "moderate": ["Govern", "Map", "Measure"],
    "high": ["Govern", "Map", "Measure", "Manage"]
  }
}
```

- [ ] **Step 4: Create `app/policy/__init__.py`** to load policy JSON

```python
import json
from functools import lru_cache
from pathlib import Path

_POLICY_DIR = Path(__file__).parent


@lru_cache(maxsize=8)
def load_json(name: str) -> dict:
    return json.loads((_POLICY_DIR / name).read_text())
```

- [ ] **Step 5: Create `app/services/scoring.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Classification, RiskTier
from app.policy import load_json

_TIER_ORDER = {RiskTier.low: 0, RiskTier.moderate: 1, RiskTier.high: 2}


@dataclass(frozen=True)
class ScoreResult:
    tier: RiskTier
    classification: Classification
    rubric_version: str
    breakdown: list[str] = field(default_factory=list)


def _matches(when: dict, answers: dict) -> bool:
    return all(answers.get(k) == v for k, v in when.items())


def score_use_case(answers: dict) -> ScoreResult:
    rubric = load_json("rubric.json")
    tier = RiskTier.low
    classification = Classification.internal
    breakdown: list[str] = []

    for rule in rubric["rules"]:
        if not _matches(rule["when"], answers):
            continue
        if "tier_min" in rule:
            candidate = RiskTier(rule["tier_min"])
            if _TIER_ORDER[candidate] > _TIER_ORDER[tier]:
                tier = candidate
                breakdown.append(f"rule {rule['id']} raised tier to {tier.value}")
        if "classification" in rule:
            classification = Classification(rule["classification"])
            breakdown.append(f"rule {rule['id']} set classification to {classification.value}")

    return ScoreResult(
        tier=tier,
        classification=classification,
        rubric_version=rubric["version"],
        breakdown=breakdown,
    )
```

- [ ] **Step 6: Run scoring tests**

Run: `pytest tests/test_scoring.py -v`
Expected: all PASS.

- [ ] **Step 7: Write failing test in `tests/test_controls.py`**

```python
from app.models import RiskTier
from app.services.controls import recommend_controls


def test_low_tier_has_base_controls_only() -> None:
    result = recommend_controls(
        tier=RiskTier.low,
        answers={"external_vendor": False, "contains_cui": False, "model_kind": "llm_api"},
    )
    assert "AC-2" in result.nist_800_53
    assert "CA-3" not in result.nist_800_53


def test_high_tier_with_vendor_adds_vendor_controls() -> None:
    result = recommend_controls(
        tier=RiskTier.high,
        answers={"external_vendor": True, "contains_cui": True, "model_kind": "llm_api"},
    )
    assert "CA-3" in result.nist_800_53
    assert "SR-3" in result.nist_800_53
    assert "SC-28" in result.nist_800_53


def test_ml_model_adds_si_7() -> None:
    result = recommend_controls(
        tier=RiskTier.moderate,
        answers={"external_vendor": False, "contains_cui": False, "model_kind": "ml_model"},
    )
    assert "SI-7" in result.nist_800_53
```

- [ ] **Step 8: Create `app/services/controls.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import RiskTier
from app.policy import load_json


@dataclass(frozen=True)
class ControlRecommendation:
    nist_800_53: list[str] = field(default_factory=list)
    ai_rmf: list[str] = field(default_factory=list)
    template_version: str = ""


def recommend_controls(*, tier: RiskTier, answers: dict) -> ControlRecommendation:
    template = load_json("template.json")
    controls: list[str] = list(template["base_controls"][tier.value])

    additional = template["additional"]
    if answers.get("external_vendor"):
        controls.extend(additional["external_vendor"])
    if answers.get("contains_cui"):
        controls.extend(additional["contains_cui"])
    if answers.get("model_kind") == "ml_model":
        controls.extend(additional["model_kind_ml_model"])

    seen: set[str] = set()
    deduped = [c for c in controls if not (c in seen or seen.add(c))]

    return ControlRecommendation(
        nist_800_53=deduped,
        ai_rmf=template["ai_rmf"][tier.value],
        template_version=template["version"],
    )
```

- [ ] **Step 9: Run control tests**

Run: `pytest tests/test_controls.py -v`
Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add app/policy app/services/scoring.py app/services/controls.py tests/test_scoring.py tests/test_controls.py
git commit -m "feat: add versioned risk scoring and control recommendation engines"
```

---

## Task 6: State Machine (`workflow.py`)

**Files:**
- Create: `app/workflow.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing test in `tests/test_workflow.py`**

```python
import pytest

from app.models import UseCaseStatus, UserRole
from app.workflow import Action, StateMachineError, allowed_actions, apply


def test_draft_to_submitted() -> None:
    new_state = apply(
        current=UseCaseStatus.draft, action=Action.submit, actor_role=UserRole.requestor
    )
    assert new_state == UseCaseStatus.submitted


def test_disallowed_action_raises() -> None:
    with pytest.raises(StateMachineError):
        apply(current=UseCaseStatus.draft, action=Action.approve, actor_role=UserRole.ao)


def test_wrong_role_raises() -> None:
    with pytest.raises(StateMachineError):
        apply(
            current=UseCaseStatus.ao_decision,
            action=Action.approve,
            actor_role=UserRole.requestor,
        )


def test_allowed_actions_for_draft() -> None:
    actions = set(allowed_actions(UseCaseStatus.draft, UserRole.requestor))
    assert Action.submit in actions
    assert Action.withdraw in actions
    assert Action.approve not in actions


def test_full_happy_path() -> None:
    state = UseCaseStatus.draft
    state = apply(current=state, action=Action.submit, actor_role=UserRole.requestor)
    assert state == UseCaseStatus.submitted
    state = apply(current=state, action=Action.auto_triage, actor_role=UserRole.requestor)
    assert state == UseCaseStatus.triage
    state = apply(
        current=state, action=Action.assign_reviewers, actor_role=UserRole.security_reviewer
    )
    assert state == UseCaseStatus.in_review
    state = apply(current=state, action=Action.auto_advance, actor_role=UserRole.ao)
    assert state == UseCaseStatus.ao_decision
    state = apply(current=state, action=Action.approve, actor_role=UserRole.ao)
    assert state == UseCaseStatus.approved


def test_withdraw_allowed_from_several_states() -> None:
    for s in (UseCaseStatus.draft, UseCaseStatus.submitted, UseCaseStatus.revision_requested):
        assert apply(current=s, action=Action.withdraw, actor_role=UserRole.requestor) == (
            UseCaseStatus.withdrawn
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `app/workflow.py`**

```python
"""State machine for use case lifecycle.

This file is the spec. Every legal transition is a row in _TRANSITIONS.
Reading this file end-to-end gives you the full workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models import UseCaseStatus, UserRole


class Action(str, Enum):
    submit = "submit"
    auto_triage = "auto_triage"
    request_revision = "request_revision"
    assign_reviewers = "assign_reviewers"
    submit_review = "submit_review"
    auto_advance = "auto_advance"
    approve = "approve"
    approve_with_conditions = "approve_with_conditions"
    reject = "reject"
    send_back = "send_back"
    resubmit = "resubmit"
    expire = "expire"
    revoke = "revoke"
    withdraw = "withdraw"


class StateMachineError(Exception):
    """Raised when a transition is not legal under the state machine."""


@dataclass(frozen=True)
class Transition:
    from_state: UseCaseStatus
    action: Action
    to_state: UseCaseStatus
    actor_roles: frozenset[UserRole]


_SYSTEM_ROLES = frozenset(UserRole)
_REQ = frozenset({UserRole.requestor})
_REVIEWERS = frozenset({UserRole.security_reviewer, UserRole.privacy_reviewer})
_AO = frozenset({UserRole.ao})
_TRIAGER = frozenset({UserRole.security_reviewer})


_TRANSITIONS: tuple[Transition, ...] = (
    Transition(UseCaseStatus.draft, Action.submit, UseCaseStatus.submitted, _REQ),
    Transition(UseCaseStatus.submitted, Action.auto_triage, UseCaseStatus.triage, _SYSTEM_ROLES),
    Transition(UseCaseStatus.triage, Action.request_revision, UseCaseStatus.revision_requested, _REVIEWERS),
    Transition(UseCaseStatus.triage, Action.assign_reviewers, UseCaseStatus.in_review, _TRIAGER),
    Transition(UseCaseStatus.in_review, Action.submit_review, UseCaseStatus.in_review, _REVIEWERS),
    Transition(UseCaseStatus.in_review, Action.auto_advance, UseCaseStatus.ao_decision, _SYSTEM_ROLES),
    Transition(UseCaseStatus.ao_decision, Action.approve, UseCaseStatus.approved, _AO),
    Transition(UseCaseStatus.ao_decision, Action.approve_with_conditions, UseCaseStatus.conditionally_approved, _AO),
    Transition(UseCaseStatus.ao_decision, Action.reject, UseCaseStatus.rejected, _AO),
    Transition(UseCaseStatus.ao_decision, Action.send_back, UseCaseStatus.revision_requested, _AO),
    Transition(UseCaseStatus.revision_requested, Action.resubmit, UseCaseStatus.submitted, _REQ),
    Transition(UseCaseStatus.approved, Action.expire, UseCaseStatus.re_review_required, _SYSTEM_ROLES),
    Transition(UseCaseStatus.conditionally_approved, Action.expire, UseCaseStatus.re_review_required, _SYSTEM_ROLES),
    Transition(UseCaseStatus.re_review_required, Action.resubmit, UseCaseStatus.submitted, _REQ),
    Transition(UseCaseStatus.approved, Action.revoke, UseCaseStatus.revoked, _AO),
    Transition(UseCaseStatus.conditionally_approved, Action.revoke, UseCaseStatus.revoked, _AO),
    Transition(UseCaseStatus.re_review_required, Action.revoke, UseCaseStatus.revoked, _AO),
    Transition(UseCaseStatus.draft, Action.withdraw, UseCaseStatus.withdrawn, _REQ),
    Transition(UseCaseStatus.submitted, Action.withdraw, UseCaseStatus.withdrawn, _REQ),
    Transition(UseCaseStatus.revision_requested, Action.withdraw, UseCaseStatus.withdrawn, _REQ),
)


def _lookup(current: UseCaseStatus, action: Action) -> Transition | None:
    for t in _TRANSITIONS:
        if t.from_state == current and t.action == action:
            return t
    return None


def apply(*, current: UseCaseStatus, action: Action, actor_role: UserRole) -> UseCaseStatus:
    t = _lookup(current, action)
    if t is None:
        raise StateMachineError(f"action {action.value} not legal from state {current.value}")
    if actor_role not in t.actor_roles:
        raise StateMachineError(
            f"role {actor_role.value} cannot perform {action.value} from {current.value}"
        )
    return t.to_state


def allowed_actions(current: UseCaseStatus, actor_role: UserRole):
    for t in _TRANSITIONS:
        if t.from_state == current and actor_role in t.actor_roles:
            yield t.action
```

- [ ] **Step 4: Run workflow tests**

Run: `pytest tests/test_workflow.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/workflow.py tests/test_workflow.py
git commit -m "feat: add hand-rolled workflow state machine with transition table"
```

---

## Task 7: Use Case Lifecycle Service (Draft, Intake, Submit)

**Files:**
- Create: `app/services/lifecycle.py`
- Test: `tests/test_lifecycle.py`

- [ ] **Step 1: Write failing test in `tests/test_lifecycle.py`**

```python
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
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="contains_pii", answer_value=True)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="contains_cui", answer_value=False)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="external_vendor", answer_value=False)
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="hosting", answer_value="agency-azure")
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="model_kind", answer_value="llm_api")
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="data_types", answer_value=["employee_qna"])

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
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="data_types", answer_value=["a"])
    svc.upsert_intake_answer(use_case_id=uc.id, question_key="data_types", answer_value=["a", "b"])
    session.commit()

    versions = session.exec(
        select(IntakeAnswer).where(IntakeAnswer.use_case_id == uc.id, IntakeAnswer.question_key == "data_types")
    ).all()
    assert {v.version for v in versions} == {1, 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lifecycle.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `app/services/lifecycle.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import (
    IntakeAnswer, StateTransition, UseCase, UseCaseStatus, User,
)
from app.services.audit import AuditLogWriter
from app.services.scoring import ScoreResult, score_use_case
from app.services.sod import SoDViolation
from app.workflow import Action, apply


class LifecycleService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditLogWriter(session)

    def create_draft(
        self,
        *,
        sponsor_id: int,
        title: str,
        business_purpose: str,
        model_name: str,
        hosting: str,
    ) -> UseCase:
        uc = UseCase(
            sponsor_id=sponsor_id,
            title=title,
            business_purpose=business_purpose,
            model_name=model_name,
            hosting=hosting,
            status=UseCaseStatus.draft,
            policy_template_version="v1",
            rubric_version="v1",
        )
        self._session.add(uc)
        self._session.flush()
        self._audit.append(
            actor_id=sponsor_id,
            action="create_draft",
            entity_type="use_case",
            entity_id=uc.id,
            payload={"title": title},
        )
        return uc

    def upsert_intake_answer(
        self, *, use_case_id: int, question_key: str, answer_value: Any
    ) -> IntakeAnswer:
        stmt = (
            select(IntakeAnswer)
            .where(
                IntakeAnswer.use_case_id == use_case_id,
                IntakeAnswer.question_key == question_key,
            )
            .order_by(IntakeAnswer.version.desc())
        )
        latest = self._session.exec(stmt).first()
        version = (latest.version + 1) if latest else 1
        row = IntakeAnswer(
            use_case_id=use_case_id,
            question_key=question_key,
            answer_value={"value": answer_value},
            version=version,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _collect_current_intake(self, use_case_id: int) -> dict[str, Any]:
        stmt = (
            select(IntakeAnswer)
            .where(IntakeAnswer.use_case_id == use_case_id)
            .order_by(IntakeAnswer.question_key, IntakeAnswer.version.desc())
        )
        rows = self._session.exec(stmt).all()
        current: dict[str, Any] = {}
        for row in rows:
            if row.question_key in current:
                continue
            current[row.question_key] = row.answer_value.get("value")
        return current

    def _record_transition(
        self,
        *,
        use_case_id: int,
        from_state: UseCaseStatus,
        to_state: UseCaseStatus,
        actor_id: int,
        action: str,
        reason: str | None = None,
        extra_payload: dict | None = None,
    ) -> None:
        self._session.add(
            StateTransition(
                use_case_id=use_case_id,
                from_state=from_state,
                to_state=to_state,
                actor_id=actor_id,
                reason=reason,
            )
        )
        payload = {"from": from_state.value, "to": to_state.value}
        if reason:
            payload["reason"] = reason
        if extra_payload:
            payload.update(extra_payload)
        self._audit.append(
            actor_id=actor_id,
            action=action,
            entity_type="use_case",
            entity_id=use_case_id,
            payload=payload,
        )

    def submit(self, *, use_case_id: int, actor_id: int) -> UseCase:
        uc = self._session.get(UseCase, use_case_id)
        if uc is None:
            raise ValueError(f"use case {use_case_id} not found")
        actor = self._session.get(User, actor_id)
        if actor is None:
            raise ValueError(f"actor {actor_id} not found")
        if actor_id != uc.sponsor_id:
            raise SoDViolation(
                f"only the sponsor may submit use case {use_case_id} (actor={actor_id})"
            )

        answers = self._collect_current_intake(use_case_id)
        score: ScoreResult = score_use_case(answers)
        new_state = apply(current=uc.status, action=Action.submit, actor_role=actor.role)
        from_state = uc.status
        uc.status = new_state
        uc.risk_tier = score.tier
        uc.classification = score.classification
        uc.rubric_version = score.rubric_version
        uc.updated_at = datetime.now(timezone.utc)
        self._session.add(uc)
        self._record_transition(
            use_case_id=uc.id,
            from_state=from_state,
            to_state=new_state,
            actor_id=actor_id,
            action="submit",
            extra_payload={
                "risk_tier": score.tier.value,
                "classification": score.classification.value,
                "breakdown": score.breakdown,
            },
        )
        return uc
```

- [ ] **Step 4: Run lifecycle tests**

Run: `pytest tests/test_lifecycle.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/lifecycle.py tests/test_lifecycle.py
git commit -m "feat: add use case lifecycle service for draft, intake, submit"
```

---

## Task 8: Reviews, Conditions, and AO Decisions

**Files:**
- Modify: `app/services/lifecycle.py` (extend with triage, assign_reviewers, submit_review, ao_decide)
- Test: `tests/test_reviews.py`

- [ ] **Step 1: Write failing test in `tests/test_reviews.py`**

```python
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
        svc.upsert_intake_answer(use_case_id=uc.id, question_key=k, answer_value=v)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reviews.py -v`
Expected: AttributeError — new methods missing.

- [ ] **Step 3: Extend `app/services/lifecycle.py`** — append the following methods to the `LifecycleService` class and add the helper methods

Add at the end of the `LifecycleService` class body (same indentation as existing methods):

```python
    # --- triage / review / AO ----------------------------------------------

    def triage(self, *, use_case_id: int, actor_id: int) -> UseCase:
        from app.services.sod import ensure_not_sponsor

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=actor_id)
        new_state = apply(
            current=uc.status, action=Action.auto_triage, actor_role=actor.role
        )
        self._transition(uc, new_state, actor_id=actor_id, action_name="auto_triage")
        return uc

    def assign_reviewers(
        self, *, use_case_id: int, actor_id: int, security_id: int, privacy_id: int
    ) -> UseCase:
        from app.models import ReviewRole
        from app.services.sod import (
            ensure_not_sponsor,
            ensure_triager_not_reviewer,
            ensure_unique_cross_cycle_roles,
        )

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)

        for candidate, role in (
            (security_id, ReviewRole.security),
            (privacy_id, ReviewRole.privacy),
        ):
            ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=candidate)
            ensure_unique_cross_cycle_roles(
                self._session, use_case_id=use_case_id, actor_id=candidate, target_role=role
            )
            ensure_triager_not_reviewer(
                self._session, use_case_id=use_case_id, actor_id=candidate, target_role=role
            )

        new_state = apply(
            current=uc.status, action=Action.assign_reviewers, actor_role=actor.role
        )
        self._transition(
            uc,
            new_state,
            actor_id=actor_id,
            action_name="assign_reviewers",
            extra_payload={"security_id": security_id, "privacy_id": privacy_id},
        )
        return uc

    def submit_review(
        self,
        *,
        use_case_id: int,
        reviewer_id: int,
        role,
        decision,
        narrative: str,
        conditions: list[dict],
    ):
        from app.models import Condition, ConditionStatus, Review, ReviewRole as _RR
        from app.services.sod import (
            ensure_not_sponsor,
            ensure_triager_not_reviewer,
            ensure_unique_cross_cycle_roles,
        )

        uc = self._require_use_case(use_case_id)
        reviewer = self._require_user(reviewer_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=reviewer_id)
        ensure_unique_cross_cycle_roles(
            self._session, use_case_id=use_case_id, actor_id=reviewer_id, target_role=role
        )
        ensure_triager_not_reviewer(
            self._session, use_case_id=use_case_id, actor_id=reviewer_id, target_role=role
        )

        review = Review(
            use_case_id=use_case_id,
            reviewer_id=reviewer_id,
            role=role,
            decision=decision,
            narrative=narrative,
        )
        self._session.add(review)
        self._session.flush()
        for c in conditions:
            self._session.add(
                Condition(
                    use_case_id=use_case_id,
                    name=c["name"],
                    description=c["description"],
                    status=ConditionStatus.proposed,
                    source_review_id=review.id,
                )
            )

        self._audit.append(
            actor_id=reviewer_id,
            action="submit_review",
            entity_type="use_case",
            entity_id=use_case_id,
            payload={
                "review_id": review.id,
                "role": role.value,
                "decision": decision.value,
                "conditions": [c["name"] for c in conditions],
            },
        )

        roles_seen = {
            r.role
            for r in self._session.exec(
                select(Review).where(Review.use_case_id == use_case_id)
            ).all()
        }
        if {_RR.security, _RR.privacy}.issubset(roles_seen):
            self._transition(
                uc,
                UseCaseStatus.ao_decision,
                actor_id=reviewer_id,
                action_name="auto_advance",
                via_state_machine=False,
            )
        return review

    def ao_decide(
        self,
        *,
        use_case_id: int,
        actor_id: int,
        decision: str,
        narrative: str | None = None,
        accepted_condition_ids="all",
        re_review_days_by_tier: dict[str, int] | None = None,
    ) -> UseCase:
        from datetime import timedelta

        from app.models import Condition, ConditionStatus, ReReview, ReReviewTrigger
        from app.services.sod import ensure_ao_clean, ensure_not_sponsor

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=actor_id)
        ensure_ao_clean(self._session, use_case_id=use_case_id, actor_id=actor_id)

        action_map = {
            "approve": (Action.approve, UseCaseStatus.approved),
            "approve_with_conditions": (
                Action.approve_with_conditions,
                UseCaseStatus.conditionally_approved,
            ),
            "reject": (Action.reject, UseCaseStatus.rejected),
            "send_back": (Action.send_back, UseCaseStatus.revision_requested),
        }
        if decision not in action_map:
            raise ValueError(f"unknown AO decision: {decision}")
        action_enum, target_state = action_map[decision]
        apply(current=uc.status, action=action_enum, actor_role=actor.role)

        if decision == "approve_with_conditions":
            stmt = select(Condition).where(
                Condition.use_case_id == use_case_id,
                Condition.status == ConditionStatus.proposed,
            )
            conds = self._session.exec(stmt).all()
            if accepted_condition_ids == "all":
                for c in conds:
                    c.status = ConditionStatus.accepted
                    self._session.add(c)
            else:
                id_set = set(accepted_condition_ids)
                for c in conds:
                    if c.id in id_set:
                        c.status = ConditionStatus.accepted
                        self._session.add(c)

        self._transition(
            uc, target_state, actor_id=actor_id, action_name=decision, reason=narrative,
            via_state_machine=False,
        )

        if target_state in (UseCaseStatus.approved, UseCaseStatus.conditionally_approved):
            defaults = re_review_days_by_tier or {"low": 365, "moderate": 180, "high": 90}
            days = defaults[uc.risk_tier.value] if uc.risk_tier else 365
            self._session.add(
                ReReview(
                    use_case_id=use_case_id,
                    due_date=datetime.now(timezone.utc) + timedelta(days=days),
                    trigger=ReReviewTrigger.scheduled,
                )
            )
        return uc

    # --- helpers ----------------------------------------------------------

    def _require_use_case(self, use_case_id: int) -> UseCase:
        uc = self._session.get(UseCase, use_case_id)
        if uc is None:
            raise ValueError(f"use case {use_case_id} not found")
        return uc

    def _require_user(self, user_id: int) -> User:
        u = self._session.get(User, user_id)
        if u is None:
            raise ValueError(f"user {user_id} not found")
        return u

    def _transition(
        self,
        uc: UseCase,
        to_state: UseCaseStatus,
        *,
        actor_id: int,
        action_name: str,
        reason: str | None = None,
        extra_payload: dict | None = None,
        via_state_machine: bool = True,
    ) -> None:
        from_state = uc.status
        uc.status = to_state
        uc.updated_at = datetime.now(timezone.utc)
        self._session.add(uc)
        self._record_transition(
            use_case_id=uc.id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            action=action_name,
            reason=reason,
            extra_payload=extra_payload,
        )
```

- [ ] **Step 4: Run review tests**

Run: `pytest tests/test_reviews.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/lifecycle.py tests/test_reviews.py
git commit -m "feat: add triage, review submission, AO decision, re-review scheduling"
```

---

## Task 9: Re-review Expiration and Material-Change Triggers

**Files:**
- Modify: `app/services/lifecycle.py` (add `check_expirations`, `trigger_material_change`)
- Test: `tests/test_re_review.py`

- [ ] **Step 1: Write failing test in `tests/test_re_review.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Classification, ReReview, RiskTier, UseCase, UseCaseStatus, UserRole,
)
from app.services.lifecycle import LifecycleService
from app.services.users import create_user


def _mk_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_check_expirations_moves_overdue_to_re_review_required() -> None:
    session = _mk_session()
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    uc = UseCase(
        sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h",
        status=UseCaseStatus.approved, risk_tier=RiskTier.low, classification=Classification.internal,
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.flush()
    session.add(
        ReReview(
            use_case_id=uc.id,
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    session.commit()

    moved = svc.check_expirations(actor_id=sponsor.id)
    session.commit()
    assert uc.id in moved
    session.refresh(uc)
    assert uc.status == UseCaseStatus.re_review_required


def test_material_change_forces_re_review() -> None:
    session = _mk_session()
    svc = LifecycleService(session)
    sponsor = create_user(session, email="s@x", name="S", role=UserRole.requestor, password="p")
    session.commit()

    uc = UseCase(
        sponsor_id=sponsor.id, title="t", business_purpose="p", model_name="m", hosting="h",
        status=UseCaseStatus.approved, risk_tier=RiskTier.low, classification=Classification.internal,
        policy_template_version="v1", rubric_version="v1",
    )
    session.add(uc)
    session.commit()

    svc.trigger_material_change(use_case_id=uc.id, actor_id=sponsor.id, reason="model swap")
    session.commit()
    session.refresh(uc)
    assert uc.status == UseCaseStatus.re_review_required
    rr = session.exec(select(ReReview).where(ReReview.use_case_id == uc.id)).first()
    assert rr is not None
    assert rr.trigger.value == "material_change"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_re_review.py -v`
Expected: AttributeError on new methods.

- [ ] **Step 3: Append methods to `LifecycleService`**

```python
    def check_expirations(self, *, actor_id: int) -> list[int]:
        from datetime import datetime, timezone

        from app.models import ReReview

        now = datetime.now(timezone.utc)
        stmt = (
            select(UseCase, ReReview)
            .join(ReReview, ReReview.use_case_id == UseCase.id)
            .where(
                UseCase.status.in_(
                    [UseCaseStatus.approved, UseCaseStatus.conditionally_approved]
                ),
                ReReview.due_date <= now,
                ReReview.completed_at.is_(None),
            )
        )
        moved: list[int] = []
        for uc, _rr in self._session.exec(stmt).all():
            self._transition(
                uc,
                UseCaseStatus.re_review_required,
                actor_id=actor_id,
                action_name="expire",
                via_state_machine=False,
            )
            moved.append(uc.id)
        return moved

    def trigger_material_change(self, *, use_case_id: int, actor_id: int, reason: str) -> UseCase:
        from app.models import ReReview, ReReviewTrigger

        uc = self._require_use_case(use_case_id)
        self._session.add(
            ReReview(
                use_case_id=use_case_id,
                due_date=datetime.now(timezone.utc),
                trigger=ReReviewTrigger.material_change,
            )
        )
        self._transition(
            uc,
            UseCaseStatus.re_review_required,
            actor_id=actor_id,
            action_name="expire",
            reason=reason,
            via_state_machine=False,
        )
        return uc
```

- [ ] **Step 4: Run re-review tests**

Run: `pytest tests/test_re_review.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/lifecycle.py tests/test_re_review.py
git commit -m "feat: add re-review expiration check and material-change trigger"
```

---

## Task 10: Decision Packet Generator (Markdown)

**Files:**
- Create: `app/services/packet.py`
- Test: `tests/test_packet.py`

- [ ] **Step 1: Write failing test in `tests/test_packet.py`**

```python
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
        svc.upsert_intake_answer(use_case_id=uc.id, question_key=k, answer_value=v)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_packet.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `app/services/packet.py`**

```python
from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    Condition, Review, ReviewPacket, StateTransition, UseCase, User,
)
from app.services.controls import recommend_controls
from app.services.lifecycle import LifecycleService
from app.services.scoring import score_use_case


def generate_markdown_packet(
    session: Session, *, use_case_id: int, generated_by: int
) -> ReviewPacket:
    uc = session.get(UseCase, use_case_id)
    if uc is None:
        raise ValueError(f"use case {use_case_id} not found")
    sponsor = session.get(User, uc.sponsor_id)

    svc = LifecycleService(session)
    answers = svc._collect_current_intake(use_case_id)
    score = score_use_case(answers)
    controls = recommend_controls(tier=score.tier, answers=answers)

    reviews = session.exec(select(Review).where(Review.use_case_id == use_case_id)).all()
    conditions = session.exec(select(Condition).where(Condition.use_case_id == use_case_id)).all()
    transitions = session.exec(
        select(StateTransition)
        .where(StateTransition.use_case_id == use_case_id)
        .order_by(StateTransition.created_at.asc())
    ).all()

    md: list[str] = []
    md.append(f"# Decision Packet — {uc.title}")
    md.append("")
    md.append(f"Sponsor: {sponsor.name} <{sponsor.email}>")
    md.append(f"Status: **{uc.status.value}**")
    md.append(f"Risk tier: **{uc.risk_tier.value if uc.risk_tier else 'unscored'}**")
    md.append(
        f"Classification: **{uc.classification.value if uc.classification else 'unscored'}**"
    )
    md.append(f"Policy template: {uc.policy_template_version}")
    md.append(f"Rubric: {uc.rubric_version}")
    md.append("")

    md.append("## Business purpose")
    md.append(uc.business_purpose)
    md.append("")

    md.append("## Intake")
    for k in sorted(answers):
        md.append(f"- **{k}**: `{answers[k]}`")
    md.append("")

    md.append("## Risk scoring breakdown")
    for b in score.breakdown or ["default low tier"]:
        md.append(f"- {b}")
    md.append("")

    md.append("## Controls")
    md.append("### NIST SP 800-53")
    for c in controls.nist_800_53:
        md.append(f"- {c}")
    md.append("### NIST AI RMF")
    for c in controls.ai_rmf:
        md.append(f"- {c}")
    md.append("")

    md.append("## Reviews")
    if not reviews:
        md.append("_No reviews submitted._")
    for r in reviews:
        reviewer = session.get(User, r.reviewer_id)
        md.append(
            f"- **{r.role.value}** by {reviewer.name} — {r.decision.value} — {r.narrative}"
        )
    md.append("")

    md.append("## Conditions")
    if not conditions:
        md.append("_None._")
    for c in conditions:
        md.append(f"- **{c.name}** [{c.status.value}]: {c.description}")
    md.append("")

    md.append("## Timeline")
    for t in transitions:
        actor = session.get(User, t.actor_id)
        actor_label = actor.name if actor else f"user-{t.actor_id}"
        reason = f" — {t.reason}" if t.reason else ""
        md.append(
            f"- {t.created_at.isoformat()} · {actor_label} · "
            f"{t.from_state.value} → {t.to_state.value}{reason}"
        )
    md.append("")

    latest = session.exec(
        select(ReviewPacket)
        .where(ReviewPacket.use_case_id == use_case_id)
        .order_by(ReviewPacket.version.desc())
    ).first()
    next_version = (latest.version + 1) if latest else 1

    packet = ReviewPacket(
        use_case_id=use_case_id,
        version=next_version,
        markdown="\n".join(md),
        generated_by=generated_by,
    )
    session.add(packet)
    session.flush()
    return packet
```

- [ ] **Step 4: Run packet tests**

Run: `pytest tests/test_packet.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/packet.py tests/test_packet.py
git commit -m "feat: add Markdown decision packet generator"
```

---

## Task 11: LLM Seam

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/base.py`
- Create: `app/llm/noop.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write failing test in `tests/test_llm.py`**

```python
from app.llm import get_llm_client
from app.llm.noop import NoopLLMClient


def test_default_client_is_noop_when_disabled(monkeypatch) -> None:
    from app import config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "ai_features_enabled", False)
    client = get_llm_client(classification="internal")
    assert isinstance(client, NoopLLMClient)


def test_cui_classification_forces_noop_even_when_enabled(monkeypatch) -> None:
    from app import config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "ai_features_enabled", True)
    client = get_llm_client(classification="cui")
    assert isinstance(client, NoopLLMClient)


def test_noop_returns_advisory_placeholder() -> None:
    client = NoopLLMClient()
    art = client.summarize_intake(use_case_title="t", intake={"k": "v"})
    assert art.advisory is True
    assert "disabled" in art.content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `app/llm/base.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class AIArtifact:
    content: str
    model: str
    generated_at: datetime
    advisory: bool = True


class LLMClient(Protocol):
    def summarize_intake(self, *, use_case_title: str, intake: dict) -> AIArtifact: ...
    def extract_red_flags(self, *, narrative: str) -> list[AIArtifact]: ...
    def suggest_controls(self, *, use_case_title: str, intake: dict) -> list[AIArtifact]: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)
```

- [ ] **Step 4: Create `app/llm/noop.py`**

```python
from __future__ import annotations

from app.llm.base import AIArtifact, _now


class NoopLLMClient:
    model: str = "noop"

    def summarize_intake(self, *, use_case_title: str, intake: dict) -> AIArtifact:
        return AIArtifact(
            content="AI features disabled for this deployment or case.",
            model=self.model,
            generated_at=_now(),
        )

    def extract_red_flags(self, *, narrative: str) -> list[AIArtifact]:
        return []

    def suggest_controls(self, *, use_case_title: str, intake: dict) -> list[AIArtifact]:
        return []
```

- [ ] **Step 5: Create `app/llm/__init__.py`**

```python
from __future__ import annotations

from app.config import settings
from app.llm.base import AIArtifact, LLMClient
from app.llm.noop import NoopLLMClient


def get_llm_client(*, classification: str | None) -> LLMClient:
    if not settings.ai_features_enabled:
        return NoopLLMClient()
    if classification == "cui":
        return NoopLLMClient()
    return NoopLLMClient()  # v1: no provider implementations wired yet


__all__ = ["AIArtifact", "LLMClient", "NoopLLMClient", "get_llm_client"]
```

- [ ] **Step 6: Run LLM tests**

Run: `pytest tests/test_llm.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/llm tests/test_llm.py
git commit -m "feat: add LLM seam with Noop default and CUI-forced-off rule"
```

---

## Task 12: REST API Surface

**Files:**
- Create: `app/routes/__init__.py`
- Create: `app/routes/use_cases.py`
- Create: `app/routes/audit.py`
- Create: `app/routes/dashboard.py`
- Modify: `app/main.py` (register routers, init DB)
- Test: `tests/test_routes.py`

- [ ] **Step 1: Write failing test in `tests/test_routes.py`**

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel

from app.main import create_app
from app.models import UserRole
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
        create_user(session, email="ao@x", name="AO", role=UserRole.ao, password="p")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routes.py -v`
Expected: route missing.

- [ ] **Step 3: Create `app/routes/__init__.py`** (empty file)

```python
```

- [ ] **Step 4: Create `app/routes/use_cases.py`**

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth import current_user
from app.db import get_session
from app.models import User
from app.services.lifecycle import LifecycleService

router = APIRouter(prefix="/api/use-cases", tags=["use-cases"])


class CreateUseCaseBody(BaseModel):
    title: str
    business_purpose: str
    model_name: str
    hosting: str


class TransitionBody(BaseModel):
    action: str
    payload: dict | None = None


class IntakeBody(BaseModel):
    answers: dict


@router.post("", status_code=201)
def create(
    body: CreateUseCaseBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict:
    svc = LifecycleService(session)
    uc = svc.create_draft(
        sponsor_id=user.id,
        title=body.title,
        business_purpose=body.business_purpose,
        model_name=body.model_name,
        hosting=body.hosting,
    )
    session.commit()
    return {"id": uc.id, "status": uc.status.value}


@router.patch("/{use_case_id}/intake")
def patch_intake(
    use_case_id: int,
    body: IntakeBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict:
    svc = LifecycleService(session)
    for k, v in body.answers.items():
        svc.upsert_intake_answer(use_case_id=use_case_id, question_key=k, answer_value=v)
    session.commit()
    return {"ok": True}


@router.post("/{use_case_id}/transitions")
def transition(
    use_case_id: int,
    body: TransitionBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict:
    svc = LifecycleService(session)
    action = body.action
    payload = body.payload or {}
    try:
        if action == "submit":
            svc.submit(use_case_id=use_case_id, actor_id=user.id)
        elif action == "triage":
            svc.triage(use_case_id=use_case_id, actor_id=user.id)
        elif action == "assign_reviewers":
            svc.assign_reviewers(
                use_case_id=use_case_id,
                actor_id=user.id,
                security_id=payload["security_id"],
                privacy_id=payload["privacy_id"],
            )
        elif action == "ao_decide":
            svc.ao_decide(
                use_case_id=use_case_id,
                actor_id=user.id,
                decision=payload["decision"],
                narrative=payload.get("narrative"),
            )
        elif action == "material_change":
            svc.trigger_material_change(
                use_case_id=use_case_id, actor_id=user.id, reason=payload.get("reason", "")
            )
        else:
            raise HTTPException(400, f"unknown action: {action}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    session.commit()
    return {"ok": True}
```

- [ ] **Step 5: Create `app/routes/audit.py`**

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.models import AuditLogEntry, User
from app.services.audit import verify_chain

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("/verify")
def verify(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict:
    ok, bad_id = verify_chain(session)
    return {"ok": ok, "first_bad_id": bad_id}


@router.get("")
def list_entries(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
    entity: str | None = None,
    id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.id.asc())
    if entity:
        stmt = stmt.where(AuditLogEntry.entity_type == entity)
    if id:
        stmt = stmt.where(AuditLogEntry.entity_id == id)
    rows = session.exec(stmt.limit(limit)).all()
    return [
        {
            "id": r.id,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
            "actor_id": r.actor_id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
```

- [ ] **Step 6: Create `app/routes/dashboard.py`**

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.models import UseCase, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def summary(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> dict:
    rows = session.exec(select(UseCase)).all()
    by_status: dict[str, int] = {}
    for uc in rows:
        by_status[uc.status.value] = by_status.get(uc.status.value, 0) + 1
    by_tier: dict[str, int] = {}
    for uc in rows:
        key = uc.risk_tier.value if uc.risk_tier else "unscored"
        by_tier[key] = by_tier.get(key, 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_tier": by_tier}
```

- [ ] **Step 7: Update `app/main.py`**

Replace the file contents with:

```python
from fastapi import FastAPI

from app.auth import login_router
from app.config import settings
from app.db import init_db
from app.routes.audit import router as audit_router
from app.routes.dashboard import router as dashboard_router
from app.routes.use_cases import router as use_case_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Governance Workbench", version="0.1.0")

    init_db()
    app.include_router(login_router)
    app.include_router(use_case_router)
    app.include_router(audit_router)
    app.include_router(dashboard_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.environment}

    return app


app = create_app()
```

- [ ] **Step 8: Run route tests**

Run: `pytest tests/test_routes.py -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add app/routes app/main.py tests/test_routes.py
git commit -m "feat: add REST surface for use cases, transitions, audit log, dashboard"
```

---

## Task 13: HTMX UI Shell

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/login.html`
- Create: `app/templates/dashboard.html`
- Create: `app/templates/use_case_new.html`
- Create: `app/templates/use_case_detail.html`
- Create: `app/routes/ui.py`
- Modify: `app/main.py` (register the UI router)
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write failing test in `tests/test_ui.py`**

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel

from app.main import create_app
from app.models import UserRole
from app.services.users import create_user


def _client(monkeypatch, tmp_path) -> TestClient:
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
    return TestClient(create_app())


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
    c.post("/login", data={"email": "r@x", "password": "p"}, follow_redirects=False)
    r = c.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui.py -v`
Expected: templates/routes missing.

- [ ] **Step 3: Create `app/templates/base.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>AI Governance Workbench</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body class="bg-slate-50 text-slate-900">
  <header class="bg-white border-b border-slate-200">
    <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
      <a href="/" class="font-semibold">AI Governance Workbench</a>
      {% if user %}
        <div class="text-sm text-slate-600">
          {{ user.name }} <span class="text-slate-400">· {{ user.role.value }}</span>
          <form method="post" action="/logout" class="inline ml-3">
            <button class="text-blue-600 hover:underline">log out</button>
          </form>
        </div>
      {% endif %}
    </div>
  </header>
  <main class="max-w-5xl mx-auto px-4 py-6">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 4: Create `app/templates/login.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-semibold mb-4">Sign in</h1>
<form method="post" action="/login" class="space-y-3 max-w-sm">
  <div>
    <label class="block text-sm">Email</label>
    <input name="email" type="email" required class="w-full border rounded px-2 py-1"/>
  </div>
  <div>
    <label class="block text-sm">Password</label>
    <input name="password" type="password" required class="w-full border rounded px-2 py-1"/>
  </div>
  <button class="bg-blue-600 text-white rounded px-4 py-1.5">Sign in</button>
</form>
{% endblock %}
```

- [ ] **Step 5: Create `app/templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-semibold mb-4">Dashboard</h1>
<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
  {% for status, n in by_status.items() %}
  <div class="bg-white border rounded p-4">
    <div class="text-xs uppercase text-slate-500">{{ status }}</div>
    <div class="text-2xl font-semibold">{{ n }}</div>
  </div>
  {% endfor %}
</div>
<section class="mt-8">
  <h2 class="text-lg font-semibold mb-2">Use cases</h2>
  <a href="/use-cases/new" class="inline-block bg-blue-600 text-white rounded px-3 py-1.5">New use case</a>
  <table class="w-full text-sm mt-3">
    <thead class="text-left text-slate-500"><tr>
      <th class="py-1">Title</th><th>Status</th><th>Tier</th><th>Sponsor</th>
    </tr></thead>
    <tbody>
    {% for uc in use_cases %}
    <tr class="border-t">
      <td class="py-1"><a class="text-blue-600 hover:underline" href="/use-cases/{{ uc.id }}">{{ uc.title }}</a></td>
      <td>{{ uc.status.value }}</td>
      <td>{{ uc.risk_tier.value if uc.risk_tier else '—' }}</td>
      <td>{{ uc.sponsor_id }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 6: Create `app/templates/use_case_new.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-semibold mb-4">New use case</h1>
<form method="post" action="/ui/use-cases" class="space-y-3 max-w-xl">
  <input name="title" placeholder="Title" required class="w-full border rounded px-2 py-1"/>
  <textarea name="business_purpose" placeholder="Business purpose" required class="w-full border rounded px-2 py-1"></textarea>
  <input name="model_name" placeholder="Model (e.g. gpt-4o)" required class="w-full border rounded px-2 py-1"/>
  <input name="hosting" placeholder="Hosting (e.g. agency-azure)" required class="w-full border rounded px-2 py-1"/>
  <button class="bg-blue-600 text-white rounded px-4 py-1.5">Create draft</button>
</form>
{% endblock %}
```

- [ ] **Step 7: Create `app/templates/use_case_detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-semibold">{{ uc.title }}</h1>
<div class="text-sm text-slate-600 mb-4">
  {{ uc.status.value }} · {{ uc.risk_tier.value if uc.risk_tier else 'unscored' }} ·
  {{ uc.classification.value if uc.classification else 'unclassified' }}
</div>

<section class="mb-6">
  <h2 class="font-semibold mb-2">Business purpose</h2>
  <p class="text-sm">{{ uc.business_purpose }}</p>
</section>

<section class="mb-6">
  <h2 class="font-semibold mb-2">Timeline</h2>
  <ul class="text-sm space-y-1">
    {% for t in transitions %}
    <li>{{ t.created_at.isoformat() }} · {{ t.from_state.value }} → {{ t.to_state.value }}{% if t.reason %} — {{ t.reason }}{% endif %}</li>
    {% endfor %}
  </ul>
</section>

<section class="mb-6">
  <h2 class="font-semibold mb-2">Actions</h2>
  {% for action in allowed %}
  <form method="post" action="/ui/use-cases/{{ uc.id }}/{{ action }}" class="inline">
    <button class="bg-slate-800 text-white rounded px-3 py-1 mr-1">{{ action }}</button>
  </form>
  {% endfor %}
</section>
{% endblock %}
```

- [ ] **Step 8: Create `app/routes/ui.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.models import StateTransition, UseCase, User
from app.services.lifecycle import LifecycleService
from app.workflow import allowed_actions

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> HTMLResponse:
    use_cases = session.exec(select(UseCase).order_by(UseCase.id.desc())).all()
    by_status: dict[str, int] = {}
    for uc in use_cases:
        by_status[uc.status.value] = by_status.get(uc.status.value, 0) + 1
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "use_cases": use_cases, "by_status": by_status},
    )


@router.get("/use-cases/new", response_class=HTMLResponse)
def new_page(
    request: Request, user: Annotated[User, Depends(current_user)]
) -> HTMLResponse:
    return templates.TemplateResponse(
        "use_case_new.html", {"request": request, "user": user}
    )


@router.post("/ui/use-cases", response_class=HTMLResponse)
def create_use_case(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
    title: Annotated[str, Form()],
    business_purpose: Annotated[str, Form()],
    model_name: Annotated[str, Form()],
    hosting: Annotated[str, Form()],
) -> RedirectResponse:
    svc = LifecycleService(session)
    uc = svc.create_draft(
        sponsor_id=user.id,
        title=title,
        business_purpose=business_purpose,
        model_name=model_name,
        hosting=hosting,
    )
    session.commit()
    return RedirectResponse(url=f"/use-cases/{uc.id}", status_code=303)


@router.get("/use-cases/{use_case_id}", response_class=HTMLResponse)
def detail(
    use_case_id: int,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> HTMLResponse:
    uc = session.get(UseCase, use_case_id)
    if uc is None:
        raise HTTPException(404)
    transitions = session.exec(
        select(StateTransition)
        .where(StateTransition.use_case_id == use_case_id)
        .order_by(StateTransition.created_at.asc())
    ).all()
    allowed = [a.value for a in allowed_actions(uc.status, user.role)]
    return templates.TemplateResponse(
        "use_case_detail.html",
        {"request": request, "user": user, "uc": uc, "transitions": transitions, "allowed": allowed},
    )


@router.post("/ui/use-cases/{use_case_id}/{action}", response_class=HTMLResponse)
def ui_transition(
    use_case_id: int,
    action: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> RedirectResponse:
    svc = LifecycleService(session)
    try:
        if action == "submit":
            svc.submit(use_case_id=use_case_id, actor_id=user.id)
        elif action == "auto_triage":
            svc.triage(use_case_id=use_case_id, actor_id=user.id)
        else:
            raise HTTPException(400, f"unsupported UI action: {action}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RedirectResponse(url=f"/use-cases/{use_case_id}", status_code=303)
```

- [ ] **Step 9: Update `app/main.py`** — include the UI router

Add the import:
```python
from app.routes.ui import router as ui_router
```
Inside `create_app`, after the other `include_router` calls:
```python
    app.include_router(ui_router)
```

- [ ] **Step 10: Run UI tests**

Run: `pytest tests/test_ui.py -v`
Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add app/templates app/routes/ui.py app/main.py tests/test_ui.py
git commit -m "feat: add HTMX/Jinja UI shell for login, dashboard, use case detail"
```

---

## Task 14: Seed Data and Three Sample Use Cases

**Files:**
- Create: `seed/users.json`
- Create: `seed/use_cases.json`
- Create: `app/seed.py`
- Modify: `app/main.py` (call seed on startup if DB empty)
- Test: `tests/test_seed.py`

- [ ] **Step 1: Create `seed/users.json`**

```json
[
  {"email": "requestor@agency.gov",   "name": "Riley Requestor",   "role": "requestor",          "password": "demo"},
  {"email": "triager@agency.gov",     "name": "Tara Triager",      "role": "security_reviewer",  "password": "demo"},
  {"email": "security@agency.gov",    "name": "Sam Security",      "role": "security_reviewer",  "password": "demo"},
  {"email": "privacy@agency.gov",     "name": "Priya Privacy",     "role": "privacy_reviewer",   "password": "demo"},
  {"email": "ao@agency.gov",          "name": "Adam AO",           "role": "ao",                 "password": "demo"},
  {"email": "ciso@agency.gov",        "name": "Cora CISO",         "role": "ciso",               "password": "demo"},
  {"email": "auditor@agency.gov",     "name": "Aaron Auditor",     "role": "auditor",            "password": "demo"}
]
```

- [ ] **Step 2: Create `seed/use_cases.json`**

```json
[
  {
    "sponsor_email": "requestor@agency.gov",
    "title": "Internal policy Q&A copilot",
    "business_purpose": "Answer employee HR and security policy questions via RAG over internal documents.",
    "model_name": "gpt-4o",
    "hosting": "agency-azure",
    "intake": {
      "contains_pii": true, "contains_cui": false, "external_vendor": false,
      "hosting": "agency-azure", "model_kind": "llm_api",
      "data_types": ["internal_policy_docs", "employee_qna"]
    }
  },
  {
    "sponsor_email": "requestor@agency.gov",
    "title": "Contract clause extraction",
    "business_purpose": "Extract clauses from procurement contracts using a commercial LLM API.",
    "model_name": "commercial-llm-1",
    "hosting": "vendor_cloud",
    "intake": {
      "contains_pii": false, "contains_cui": true, "external_vendor": true,
      "hosting": "vendor_cloud", "model_kind": "llm_api",
      "data_types": ["contract_terms", "vendor_identities"]
    }
  },
  {
    "sponsor_email": "requestor@agency.gov",
    "title": "Facility predictive maintenance",
    "business_purpose": "Predict HVAC failures from building telemetry using an in-house ML model.",
    "model_name": "hvac-rf-v1",
    "hosting": "on-prem",
    "intake": {
      "contains_pii": false, "contains_cui": false, "external_vendor": false,
      "hosting": "on-prem", "model_kind": "ml_model",
      "data_types": ["facility_telemetry"]
    }
  }
]
```

- [ ] **Step 3: Create `app/seed.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine
from app.models import User, UserRole
from app.services.lifecycle import LifecycleService
from app.services.users import create_user

_SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


def seed_if_empty() -> None:
    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            return
        users_data = json.loads((_SEED_DIR / "users.json").read_text())
        email_to_id: dict[str, int] = {}
        for u in users_data:
            created = create_user(
                session,
                email=u["email"], name=u["name"],
                role=UserRole(u["role"]), password=u["password"],
            )
            email_to_id[u["email"]] = created.id
        session.commit()

        cases = json.loads((_SEED_DIR / "use_cases.json").read_text())
        svc = LifecycleService(session)
        for case in cases:
            sponsor_id = email_to_id[case["sponsor_email"]]
            uc = svc.create_draft(
                sponsor_id=sponsor_id,
                title=case["title"],
                business_purpose=case["business_purpose"],
                model_name=case["model_name"],
                hosting=case["hosting"],
            )
            for k, v in case["intake"].items():
                svc.upsert_intake_answer(use_case_id=uc.id, question_key=k, answer_value=v)
            svc.submit(use_case_id=uc.id, actor_id=sponsor_id)
        session.commit()
```

- [ ] **Step 4: Update `app/main.py`** — call seed after `init_db()`

Add the import:
```python
from app.seed import seed_if_empty
```
Inside `create_app`, after `init_db()`:
```python
    seed_if_empty()
```

- [ ] **Step 5: Write test in `tests/test_seed.py`**

```python
from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel, select

from app.models import UseCase, User
from app.seed import seed_if_empty


def test_seed_creates_users_and_cases(monkeypatch, tmp_path) -> None:
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    new_engine = _ce(cfg_mod.settings.database_url)
    from app import db as db_mod
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)

    seed_if_empty()

    with Session(new_engine) as session:
        users = session.exec(select(User)).all()
        assert len(users) == 7
        cases = session.exec(select(UseCase)).all()
        assert len(cases) == 3
        titles = {c.title for c in cases}
        assert "Internal policy Q&A copilot" in titles
        assert "Contract clause extraction" in titles
        assert "Facility predictive maintenance" in titles


def test_seed_is_idempotent(monkeypatch, tmp_path) -> None:
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    new_engine = _ce(cfg_mod.settings.database_url)
    from app import db as db_mod
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)

    seed_if_empty()
    seed_if_empty()

    with Session(new_engine) as session:
        assert len(session.exec(select(User)).all()) == 7
        assert len(session.exec(select(UseCase)).all()) == 3
```

- [ ] **Step 6: Run seed tests**

Run: `pytest tests/test_seed.py -v`
Expected: both PASS.

- [ ] **Step 7: Commit**

```bash
git add seed app/seed.py app/main.py tests/test_seed.py
git commit -m "feat: seed demo users and three sample use cases on first boot"
```

---

## Task 15: Docker Packaging and README

**Files:**
- Create: `docker/Dockerfile`
- Create: `docker/compose.yml`
- Create: `README.md`

- [ ] **Step 1: Create `docker/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY app ./app
COPY seed ./seed

RUN mkdir -p /app/data/attachments

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `docker/compose.yml`**

```yaml
services:
  workbench:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    image: ai-governance-workbench:dev
    ports:
      - "8000:8000"
    volumes:
      - workbench-data:/app/data
    environment:
      DATABASE_URL: sqlite:////app/data/workbench.db
      AI_FEATURES_ENABLED: "false"
      SESSION_SECRET: dev-only-change-me
      ENVIRONMENT: demo

volumes:
  workbench-data:
```

- [ ] **Step 3: Create `README.md`**

````markdown
# AI Governance Review and Approval Workbench

A lightweight internal platform that manages intake, review, approval, and monitoring of proposed AI use cases in a regulated organization.

See `docs/superpowers/specs/` for the scoping brief and design spec.

## Quickstart (demo)

```bash
make demo
# visit http://localhost:8000/login
# log in as any seeded user (password: demo):
#   requestor@agency.gov
#   ao@agency.gov
#   security@agency.gov
#   privacy@agency.gov
#   ciso@agency.gov
#   auditor@agency.gov
```

Three sample use cases are seeded on first boot, each exercising a different risk axis.

## Development

```bash
make install
make test
make run
```

## Layout

- `app/` — application code
- `app/services/` — business logic (lifecycle, scoring, controls, audit, SoD, packet)
- `app/workflow.py` — the one-file state machine
- `app/policy/` — versioned scoring rubric + control template JSON
- `tests/` — unit and integration tests (pytest)
- `seed/` — seed users and sample use cases
- `docs/superpowers/` — spec and plan

## Security posture

See design spec §9 "Failure Modes". Demo defaults:
- Local accounts only (no SSO)
- AI features disabled
- Session cookie signed with `SESSION_SECRET` — change for any non-laptop use
````

- [ ] **Step 4: Build and run the container**

Run: `docker compose -f docker/compose.yml up --build`
Expected: workbench starts on :8000; `curl http://localhost:8000/healthz` returns `{"status":"ok","env":"demo"}`.

- [ ] **Step 5: Commit**

```bash
git add docker README.md
git commit -m "chore: add Dockerfile, compose config, and README"
```

---

## Final Verification Task

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Verify the audit chain on the demo DB**

```bash
make demo &
sleep 5
curl -c cookies.txt -X POST 'http://localhost:8000/login' \
  -d 'email=auditor@agency.gov&password=demo' -L
curl -b cookies.txt 'http://localhost:8000/api/audit-log/verify'
```
Expected: `{"ok":true,"first_bad_id":null}`.

- [ ] **Step 3: Walk one seeded case through the workflow**

- Log in as `requestor@agency.gov`, open "Internal policy Q&A copilot".
- Log out; log in as `triager@agency.gov` and move it through triage.
- Log in as `security@agency.gov` and `privacy@agency.gov` to submit reviews.
- Log in as `ao@agency.gov` and approve with conditions.
- Generate the decision packet via `POST /api/use-cases/{id}/packet` (route planned for v0.2; in v1 use `generate_markdown_packet` through the REPL or add a route in a follow-on plan).

- [ ] **Step 4: Tag a release**

Run: `git tag v0.1.0`

---

## Known Gaps (follow-on plans)

The following spec items are intentionally not broken into tasks in this plan. Each is a coherent follow-on increment:

1. **Attachment upload endpoint.** The `attachment` table and content-addressed filesystem layout are defined (Task 1, design spec §7.2), but the upload/download route and service method are not. Add a Task for `POST /api/use-cases/{id}/attachments` (multipart, SHA-256 on write, filesystem write under `data/attachments/<prefix>/<sha256>`, DB row insert, audit entry) and a matching download route (`GET /api/attachments/{id}`). Estimated one task, ~6 steps.
2. **End-to-end integration test.** A single pytest that drives one use case from `create_draft` through `approve_with_conditions` and asserts the resulting decision packet content would catch integration regressions that the per-task tests miss. Estimated one task, ~3 steps.
3. **Decision packet REST route.** `generate_markdown_packet` exists as a service function (Task 10); wrapping it as `POST /api/use-cases/{id}/packet` and `GET /api/use-cases/{id}/packet?fmt=md` is not yet broken out. Estimated one task, ~4 steps.
4. **PDF rendering via WeasyPrint.** Optional extra; keep the container lean in v1.
5. **Alembic migrations.** V1 uses `SQLModel.metadata.create_all`; production needs real migrations. Set up when moving off SQLite.

These do not block a working v1 demo. The seeded three use cases walk through the full workflow using the REST and UI surfaces defined in Tasks 12 and 13.
