# Dashboard "Expiring Soon" Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface re-reviews due within 30 days on `/api/dashboard` (JSON) and the `/` dashboard page (HTML).

**Architecture:** Add a small service module (`app/services/expiring.py`) that returns a list of `ExpiringRow` dataclasses by joining `ReReview` to `UseCase` and filtering on `due_date`, `completed_at`, and parent `status`. The JSON dashboard route includes the rows under an `expiring_soon` key. The HTML dashboard route fetches the same rows and passes them to a new section in `dashboard.html`.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Jinja2, pytest, TestClient.

**Spec:** `docs/superpowers/specs/2026-04-25-dashboard-expiring-soon-design.md`

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| NEW | `app/services/expiring.py` | `ExpiringRow` dataclass, `EXPIRING_THRESHOLD_DAYS = 30`, `expiring_soon()` query |
| NEW | `tests/test_expiring.py` | 10 unit tests for the service |
| NEW | `tests/test_dashboard.py` | 3 JSON route tests + 2 HTML e2e tests |
| MODIFIED | `app/routes/dashboard.py` | Call `expiring_soon()` and add `expiring_soon` key to response |
| MODIFIED | `app/routes/ui.py` (function `dashboard`, lines 34-48) | Call `expiring_soon()` and pass list to template context |
| MODIFIED | `app/templates/dashboard.html` (insert after the existing tier cards section, line 53) | New panel section |

---

## Task 1: Service module — `app/services/expiring.py`

**Files:**
- Create: `app/services/expiring.py`
- Test: `tests/test_expiring.py`

### - [ ] Step 1: Write the failing tests

Create `tests/test_expiring.py` with all unit tests:

```python
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.models import (
    ReReview,
    ReReviewTrigger,
    UseCase,
    UseCaseStatus,
    User,
    UserRole,
)
from app.services.expiring import EXPIRING_THRESHOLD_DAYS, ExpiringRow, expiring_soon


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(email="r@x", name="R", role=UserRole.requestor, password_hash="x"))
        s.commit()
        yield s


def _make_uc(session: Session, *, status: UseCaseStatus, title: str = "uc") -> UseCase:
    uc = UseCase(
        title=title,
        business_purpose="bp",
        model_name="m",
        hosting="h",
        sponsor_id=1,
        status=status,
    )
    session.add(uc)
    session.commit()
    session.refresh(uc)
    return uc


def _make_rereview(
    session: Session, *, use_case_id: int, due_in_days: int, completed: bool = False
) -> ReReview:
    due = datetime.now(timezone.utc) + timedelta(days=due_in_days)
    rr = ReReview(
        use_case_id=use_case_id,
        due_date=due,
        trigger=ReReviewTrigger.scheduled,
        completed_at=datetime.now(timezone.utc) if completed else None,
    )
    session.add(rr)
    session.commit()
    session.refresh(rr)
    return rr


def test_default_threshold_constant():
    assert EXPIRING_THRESHOLD_DAYS == 30


def test_empty_db_returns_empty_list(session):
    assert expiring_soon(session) == []


def test_due_in_5_days_with_approved_parent_is_included(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=5)
    rows = expiring_soon(session)
    assert len(rows) == 1
    assert rows[0].use_case_id == uc.id
    assert rows[0].title == "uc"
    assert rows[0].days_remaining in (4, 5)  # tolerance for clock drift


def test_due_in_60_days_is_excluded(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=60)
    assert expiring_soon(session) == []


def test_re_review_required_parent_is_excluded(session):
    uc = _make_uc(session, status=UseCaseStatus.re_review_required)
    _make_rereview(session, use_case_id=uc.id, due_in_days=5)
    assert expiring_soon(session) == []


def test_terminal_status_parents_are_excluded(session):
    for status in (UseCaseStatus.revoked, UseCaseStatus.rejected, UseCaseStatus.withdrawn):
        uc = _make_uc(session, status=status, title=f"uc-{status.value}")
        _make_rereview(session, use_case_id=uc.id, due_in_days=5)
    assert expiring_soon(session) == []


def test_completed_rereview_is_excluded(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=5, completed=True)
    assert expiring_soon(session) == []


def test_results_ordered_by_due_date_ascending(session):
    uc1 = _make_uc(session, status=UseCaseStatus.approved, title="later")
    _make_rereview(session, use_case_id=uc1.id, due_in_days=20)
    uc2 = _make_uc(session, status=UseCaseStatus.conditionally_approved, title="sooner")
    _make_rereview(session, use_case_id=uc2.id, due_in_days=3)
    rows = expiring_soon(session)
    assert [r.title for r in rows] == ["sooner", "later"]


def test_custom_threshold_honored(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=10)
    assert expiring_soon(session, within_days=7) == []
    assert len(expiring_soon(session, within_days=14)) == 1


def test_past_due_row_has_negative_days_remaining(session):
    uc = _make_uc(session, status=UseCaseStatus.approved)
    _make_rereview(session, use_case_id=uc.id, due_in_days=-3)
    rows = expiring_soon(session)
    assert len(rows) == 1
    assert rows[0].days_remaining in (-4, -3)
```

### - [ ] Step 2: Run tests to verify they fail

Run: `venv/bin/pytest tests/test_expiring.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.expiring'`.

### - [ ] Step 3: Implement `app/services/expiring.py`

Create `app/services/expiring.py`:

```python
"""Service: list ReReviews due within a soft window (default 30 days).

Used by the dashboard surfaces (JSON + HTML) so reviewers can see which
post-approval re-reviews are coming due. Rows whose parent UseCase is no
longer in an active approved state are excluded — those are tracked by
status counts elsewhere or are terminal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import ReReview, UseCase, UseCaseStatus

EXPIRING_THRESHOLD_DAYS = 30

_ACTIVE_APPROVED_STATUSES = (
    UseCaseStatus.approved,
    UseCaseStatus.conditionally_approved,
)


@dataclass(frozen=True)
class ExpiringRow:
    use_case_id: int
    title: str
    due_date: datetime
    days_remaining: int


def expiring_soon(
    session: Session, *, within_days: int = EXPIRING_THRESHOLD_DAYS
) -> list[ExpiringRow]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=within_days)
    stmt = (
        select(ReReview, UseCase)
        .join(UseCase, ReReview.use_case_id == UseCase.id)
        .where(
            ReReview.due_date <= cutoff,
            ReReview.completed_at.is_(None),
            UseCase.status.in_(_ACTIVE_APPROVED_STATUSES),
        )
        .order_by(ReReview.due_date.asc())
    )
    return [
        ExpiringRow(
            use_case_id=uc.id,
            title=uc.title,
            due_date=rr.due_date,
            days_remaining=(rr.due_date - now).days,
        )
        for rr, uc in session.exec(stmt).all()
    ]
```

### - [ ] Step 4: Run tests to verify they pass

Run: `venv/bin/pytest tests/test_expiring.py -v`

Expected: PASS — all 10 tests green.

### - [ ] Step 5: Commit

Stage the new files and commit with message:
`Add expiring_soon service for dashboard re-review tracking`

Run:
```
git add app/services/expiring.py tests/test_expiring.py
git commit -m "Add expiring_soon service for dashboard re-review tracking"
```

---

## Task 2: JSON endpoint — `/api/dashboard`

**Files:**
- Modify: `app/routes/dashboard.py`
- Test: `tests/test_dashboard.py`

### - [ ] Step 1: Write the failing route tests

Create `tests/test_dashboard.py`:

```python
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
```

### - [ ] Step 2: Run tests to verify they fail

Run: `venv/bin/pytest tests/test_dashboard.py -v`

Expected: `test_api_dashboard_requires_auth` PASSES (auth already enforced). The other two FAIL with `KeyError: 'expiring_soon'` or `assert 'expiring_soon' in body`.

### - [ ] Step 3: Modify `app/routes/dashboard.py`

Replace the file contents with:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import current_user
from app.db import get_session
from app.models import UseCase, User
from app.services.expiring import expiring_soon

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

    expiring_rows = expiring_soon(session)
    return {
        "total": len(rows),
        "by_status": by_status,
        "by_tier": by_tier,
        "expiring_soon": {
            "count": len(expiring_rows),
            "items": [
                {
                    "use_case_id": r.use_case_id,
                    "title": r.title,
                    "due_date": r.due_date.isoformat(),
                    "days_remaining": r.days_remaining,
                }
                for r in expiring_rows
            ],
        },
    }
```

### - [ ] Step 4: Run tests to verify they pass

Run: `venv/bin/pytest tests/test_dashboard.py -v`

Expected: All 3 tests PASS.

Then run the full suite to confirm no regressions:

Run: `venv/bin/pytest -q`

Expected: All tests pass.

### - [ ] Step 5: Commit

Run:
```
git add app/routes/dashboard.py tests/test_dashboard.py
git commit -m "Surface expiring_soon in /api/dashboard JSON response"
```

---

## Task 3: HTML dashboard page — render the widget

**Files:**
- Modify: `app/routes/ui.py` (function `dashboard`, lines 34-48)
- Modify: `app/templates/dashboard.html` (insert new section after the existing tier-cards `</section>` on line 53)
- Test: `tests/test_dashboard.py` (extend with two e2e tests)

### - [ ] Step 1: Write the failing end-to-end tests

Append to `tests/test_dashboard.py`:

```python
def test_dashboard_html_renders_expiring_panel(monkeypatch, tmp_path) -> None:
    client, engine = _fresh_client(monkeypatch, tmp_path)
    _seed_due_rereview(engine, due_in_days=10, title="policy copilot")
    _login(client)
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert "Re-reviews due (next 30 days)" in html
    assert "policy copilot" in html


def test_dashboard_html_empty_state_when_no_due_rereviews(monkeypatch, tmp_path) -> None:
    client, _ = _fresh_client(monkeypatch, tmp_path)
    _login(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "No re-reviews due in the next 30 days." in r.text
```

### - [ ] Step 2: Run tests to verify they fail

Run: `venv/bin/pytest tests/test_dashboard.py::test_dashboard_html_renders_expiring_panel tests/test_dashboard.py::test_dashboard_html_empty_state_when_no_due_rereviews -v`

Expected: FAIL with `AssertionError: 'Re-reviews due (next 30 days)' not in html` (and similar for empty state).

### - [ ] Step 3: Modify `app/routes/ui.py`

In the `dashboard` function (lines 34-48):

a) Add this import alongside the other service import:

```python
from app.services.expiring import expiring_soon
```

b) Replace the function body (lines 34-48) with:

```python
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
    expiring_rows = expiring_soon(session)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "use_cases": use_cases,
            "by_status": by_status,
            "expiring_rows": expiring_rows,
        },
    )
```

### - [ ] Step 4: Modify `app/templates/dashboard.html`

After the existing tier cards section closes (`</section>` on line 53), insert this block:

```html
<section class="card overflow-hidden mb-8">
  <div class="px-6 py-4 border-b border-border">
    <h2 class="text-base font-semibold">Re-reviews due (next 30 days)</h2>
    <p class="text-[12px] text-mutedfg mt-0.5">{{ expiring_rows|length }} record{{ '' if expiring_rows|length == 1 else 's' }}</p>
  </div>
  {% if expiring_rows %}
  <table class="t">
    <thead>
      <tr>
        <th style="width: 8%;">ID</th>
        <th style="width: 52%;">Use case</th>
        <th style="width: 20%;">Due</th>
        <th style="width: 20%;">Days remaining</th>
      </tr>
    </thead>
    <tbody>
      {% for row in expiring_rows %}
      <tr>
        <td class="font-mono text-mutedfg tabnum">{{ '%03d' % row.use_case_id }}</td>
        <td><a href="/use-cases/{{ row.use_case_id }}" class="link">{{ row.title }}</a></td>
        <td class="text-[13px] text-mutedfg tabnum">{{ row.due_date.strftime('%Y-%m-%d') }}</td>
        <td>
          {% if row.days_remaining < 0 %}
            <span class="badge badge-high"><span class="badge-dot"></span>{{ -row.days_remaining }} days overdue</span>
          {% elif row.days_remaining <= 7 %}
            <span class="badge badge-high"><span class="badge-dot"></span>{{ row.days_remaining }} days</span>
          {% else %}
            <span class="badge badge-moderate"><span class="badge-dot"></span>{{ row.days_remaining }} days</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="px-6 py-10 text-center text-[13px] text-mutedfg">
    No re-reviews due in the next 30 days.
  </div>
  {% endif %}
</section>
```

### - [ ] Step 5: Run tests to verify they pass

Run: `venv/bin/pytest tests/test_dashboard.py -v`

Expected: All 5 tests in `test_dashboard.py` PASS.

Re-run full suite:

Run: `venv/bin/pytest -q`

Expected: All tests pass.

### - [ ] Step 6: Manual end-to-end smoke test

Boot the app and verify the widget renders.

a) Empty-state check (no fixture re-reviews):
```
make demo
```

In a browser:

1. Visit `http://localhost:8000/login`.
2. Log in as `auditor@agency.gov` / `demo`.
3. The dashboard should now show a **"Re-reviews due (next 30 days)"** panel containing the empty-state message.

b) Populated-state check — open a Python shell against the running DB and insert a fixture re-review:

```
venv/bin/python -c "
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from app.db import engine
from app.models import ReReview, ReReviewTrigger, UseCase, UseCaseStatus

with Session(engine) as s:
    uc = s.exec(select(UseCase).limit(1)).first()
    uc.status = UseCaseStatus.approved
    s.add(uc)
    s.add(ReReview(
        use_case_id=uc.id,
        due_date=datetime.now(timezone.utc) + timedelta(days=10),
        trigger=ReReviewTrigger.scheduled,
    ))
    s.commit()
"
```

Refresh `/` and confirm the use case title appears in the panel with a "10 days" badge.

Tear down: `Ctrl+C` on `make demo` (or `docker compose down` if running detached).

### - [ ] Step 7: Commit

Run:
```
git add app/routes/ui.py app/templates/dashboard.html tests/test_dashboard.py
git commit -m "Render Re-reviews due panel on dashboard page"
```

---

## Self-Review Checklist (engineer should run before reporting done)

- [ ] All 10 unit tests in `tests/test_expiring.py` pass.
- [ ] All 5 tests in `tests/test_dashboard.py` pass.
- [ ] Full `pytest -q` is green (no regressions in existing tests).
- [ ] Manual e2e: dashboard page renders the panel both in empty and populated state.
- [ ] No new files outside the ones listed in File Structure.
- [ ] Three commits land (one per task).
