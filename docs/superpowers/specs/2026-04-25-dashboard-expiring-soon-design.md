# Dashboard "Expiring Soon" Widget — Design

**Date:** 2026-04-25
**Status:** Approved (pending spec review)
**Closes:** Brief gap "dashboard for open, approved, rejected, **and expiring** reviews"

## Problem

The current dashboard endpoint (`app/routes/dashboard.py`) returns `total`, `by_status`, and `by_tier` only. The project brief explicitly calls for visibility into "expiring" reviews — re-reviews whose `due_date` is approaching — and there is no surface (API or UI) for this today. Reviewers cannot answer "what re-reviews are coming due in the next month?" without ad-hoc querying.

## Goal

Surface re-reviews due within the next 30 days on both `/api/dashboard` and the dashboard HTML page, so reviewers can see at a glance which approved use cases need attention soon.

Non-goals:

- Active notifications (email, in-app banner) — that is a separate item (#37).
- Configurable threshold via env var — defer until a real need surfaces.
- Pagination on the items list — bounded set in a governance workbench.

## Design

### Service layer

New module `app/services/expiring.py`:

```python
EXPIRING_THRESHOLD_DAYS = 30

@dataclass(frozen=True)
class ExpiringRow:
    use_case_id: int
    title: str
    due_date: datetime
    days_remaining: int  # negative if past due

def expiring_soon(
    session: Session, *, within_days: int = EXPIRING_THRESHOLD_DAYS
) -> list[ExpiringRow]: ...
```

Selection rule:

- Join `ReReview` to `UseCase`.
- Include rows where `ReReview.due_date <= now + within_days` AND `UseCase.status IN (approved, conditionally_approved)`.
- **Exclude** use cases already in `re_review_required` — they have already expired and the workflow has moved on. They show up in `by_status` instead.
- **Exclude** revoked, rejected, withdrawn use cases.
- Order ascending by `due_date` so the soonest-due appears first.
- `days_remaining = (due_date - now).days` (Python `timedelta.days`, which truncates fractional days toward negative infinity). Negative values indicate past due — a late re-review whose status has not yet been advanced by `check_expirations`.

### API layer

`app/routes/dashboard.py` adds one key to the existing response:

```json
{
  "total": 12,
  "by_status": { "approved": 5, "in_review": 4, ... },
  "by_tier": { "low": 6, "moderate": 4, "high": 2 },
  "expiring_soon": {
    "count": 3,
    "items": [
      {
        "use_case_id": 7,
        "title": "Policy Q&A copilot",
        "due_date": "2026-05-10T00:00:00Z",
        "days_remaining": 15
      }
    ]
  }
}
```

Auth unchanged: any authenticated user (`current_user`).

### UI layer

`app/templates/dashboard.html` adds a panel below the existing status/tier panels:

- Header: **"Re-reviews due (next 30 days)"**
- Empty state: "No re-reviews due in the next 30 days."
- Populated: a small table with columns "Use case", "Due", "Days remaining". Each title links to `/use-cases/{id}`.
- Past-due rows render `days_remaining` as e.g. `"5 days overdue"` in a warning style.

### Failure modes

- DB error → propagates as 500 (consistent with rest of app).
- Empty re-review table → returns `count: 0, items: []` and renders the empty-state message.
- Time zone: all comparisons use `datetime.now(timezone.utc)`; existing `UtcDateTime` column type guarantees stored values are UTC.

## Tests

**Unit tests — `tests/test_expiring.py`:**

1. Empty DB → empty list.
2. Re-review due in 5 days, parent `approved` → included, `days_remaining = 5`.
3. Re-review due in 60 days → excluded (outside threshold).
4. Re-review due in 5 days but parent `re_review_required` → excluded.
5. Re-review due in 5 days but parent `revoked` / `rejected` / `withdrawn` → excluded.
6. Two re-reviews returned in ascending `due_date` order.
7. Custom `within_days=7` honored.
8. Past-due row (due 3 days ago, parent still `approved`) → included with negative `days_remaining`.

**Route test — new `tests/test_dashboard.py`:**

9. `GET /api/dashboard` without auth → 401.
10. `GET /api/dashboard` with auth, no re-reviews → response includes `expiring_soon: {count: 0, items: []}`.
11. `GET /api/dashboard` with auth, one due re-review → response includes the row with correct shape and ISO-8601 `due_date`.

**End-to-end test — `tests/test_dashboard.py`:**

12. Seed approved use case + re-review due in 10 days, log in, request `GET /dashboard` HTML, assert the panel header and the use case title appear in the rendered page.

## Files touched

| Action | Path |
|---|---|
| NEW | `app/services/expiring.py` |
| NEW | `tests/test_expiring.py` |
| NEW | `tests/test_dashboard.py` |
| MODIFIED | `app/routes/dashboard.py` |
| MODIFIED | `app/templates/dashboard.html` |
| NEW | `docs/superpowers/specs/2026-04-25-dashboard-expiring-soon-design.md` (this file) |
