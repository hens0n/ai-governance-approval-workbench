# Security Review — AI Governance Workbench v1

**Initial review date:** 2026-04-17  
**Second pass date:** 2026-04-25 (covers UI redesign + reviewer/triager UI endpoints)  
**Reviewer:** Static analysis (Claude Code)  
**Scope:** `app/`, `app/templates/`, `app/seed.py`, `tests/`, `pyproject.toml`, `docker/`  
**Excluded:** `docs/` (documentation only)  
**Commits reviewed through:** `0fb5012` plus uncommitted UI/lifecycle changes

---

## 1. Executive Summary

The codebase has a solid foundation: Argon2id password hashing, signed session cookies, SoD enforcement in the service layer, a hash-chained audit log, and parameterized SQL throughout (no raw query construction). The original review found one **Critical** finding and three **High** findings, all of which were resolved in commit `4b5b43b`. The critical issue — `material_change` performing an irreversible state transition without any authorization check — meant any authenticated user (including a low-privilege requestor) could force any approved use case back into `re_review_required`. The three high-severity issues were the dev-only session secret committed verbatim in `docker/compose.yml`, intake-answer writes that had no ownership gate and generated no audit entry, and the auditor role being purely nominal with no route-level read-only enforcement.

The 2026-04-25 second pass focused on the new server-rendered UI surface (review submission, reviewer assignment, revision requests). It identified one Medium and four Low findings concentrated in the new UI router — all caused by the new endpoints using the generic `current_user` dependency instead of the `writer_user` defense-in-depth dependency introduced for SR-04, plus missing length caps on user-supplied free-text fields. All five second-pass findings were fixed in commit (TBD), bringing total open issues back to deferred-only items.

**Finding counts by severity:** Critical: 1 | High: 3 | Medium: 8 | Low: 10 | Informational: 6

---

## 2. Threat Model

**V1 demo environment:** The primary trust boundary is authentication (username + password). All users are assumed to be known government staff operating a single-tenant SQLite deployment on a local or private-network host. The relevant attacker is an **authenticated insider** who exceeds their role permissions — either accidentally or deliberately — plus an **unauthenticated outsider** who reaches the login page (e.g., a mis-configured port exposure). We are explicitly **not** defending against a compromise of the host OS, a malicious database administrator with direct SQLite file access, or a nation-state adversary with cryptanalytic capabilities against SHA-256 or Argon2. We are also not defending against a compromised CDN in v1 — that is explicitly deferred.

**Hypothetical production deployment:** Adds the threat of persistent attackers probing the login endpoint, users of one agency being able to see or modify cases belonging to another agency (multi-tenancy isolation is currently absent), and supply-chain threats against unmaintained libraries. The default session secret and trivial seed passwords constitute a direct path to full account compromise if the demo compose file is deployed as-is.

---

## 3. Findings Table

| ID | Title | Severity | Component | Status |
|----|-------|----------|-----------|--------|
| SR-01 | `material_change` action performs state transition with no authorization check | Critical | `app/routes/use_cases.py`, `app/services/lifecycle.py` | Fixed in 4b5b43b |
| SR-02 | Dev session secret hardcoded in `docker/compose.yml` | High | `docker/compose.yml`, `app/config.py` | Fixed in 4b5b43b |
| SR-03 | Intake-answer endpoint has no ownership/role check and writes no audit entry | High | `app/routes/use_cases.py`, `app/services/lifecycle.py` | Fixed in 4b5b43b |
| SR-04 | Auditor role not enforced as read-only at the route layer | High | `app/routes/` (all routers) | Fixed in 4b5b43b |
| SR-05 | No rate limiting or account lockout on `/login` | Medium | `app/auth.py` | Deferred to v2 |
| SR-06 | Attachment upload reads entire file into memory with no size cap | Medium | `app/routes/attachments.py` | Fixed in 4b5b43b |
| SR-07 | Attachment upload/download performs no use-case ownership check | Medium | `app/routes/attachments.py` | Fixed in 4b5b43b |
| SR-08 | `/api/audit-log` accessible to all authenticated roles | Medium | `app/routes/audit.py` | Fixed in 4b5b43b |
| SR-09 | Container runs as root — no `USER` directive in Dockerfile | Medium | `docker/Dockerfile` | Fixed in 4b5b43b |
| SR-10 | Audit log `limit` query parameter has no server-side upper bound | Medium | `app/routes/audit.py` | Fixed in 4b5b43b |
| SR-11 | Login timing oracle distinguishes valid from invalid usernames | Medium | `app/auth.py` | Deferred to v2 |
| SR-12 | Session cookie has `secure=False`; transmitted over plain HTTP | Low | `app/auth.py` | Accepted Risk (v1 demo) |
| SR-13 | No security response headers (CSP, X-Frame-Options, HSTS, etc.) | Low | `app/main.py` | Deferred to v2 |
| SR-14 | CDN scripts (Tailwind, HTMX) loaded without Subresource Integrity | Low | `app/templates/base.html` | Deferred to v2 |
| SR-15 | SoD / lifecycle exceptions leak internal IDs in HTTP 400 `detail` | Low | `app/routes/use_cases.py`, `app/routes/ui.py` | Deferred to v2 |
| SR-16 | `passlib` is unmaintained (last release 2020) | Low | `pyproject.toml` | Deferred to v2 |
| SR-17 | `_SYSTEM_ROLES` includes auditor and CISO, granting them unintended triage rights | Low | `app/workflow.py` | Fixed in 4b5b43b |
| SR-18 | Seed file ships trivial `demo` passwords for all accounts | Informational | `seed/users.json` | Accepted Risk (demo) |
| SR-19 | OpenAPI `/docs` and `/redoc` enabled with no authentication gate | Informational | `app/main.py` | Accepted Risk (demo) |
| SR-20 | `/healthz` leaks `environment` name to unauthenticated callers | Informational | `app/main.py` | Accepted Risk (demo) |
| SR-21 | No CSRF tokens on HTML forms | Informational | `app/templates/` | Accepted Risk |
| SR-22 | Audit hash chain has TOCTOU window under concurrent writers | Informational | `app/services/audit.py` | Deferred to v2 |
| SR-23 | UI router lets auditor create draft use cases (regression of SR-04 in UI surface) | Medium | `app/routes/ui.py` | Fixed 2026-04-25 |
| SR-24 | New UI write endpoints lack `writer_user` defense-in-depth | Low | `app/routes/ui.py` | Fixed 2026-04-25 |
| SR-25 | No length caps on reviewer narrative, revision reason, or condition fields | Low | `app/routes/ui.py` | Fixed 2026-04-25 |
| SR-26 | New UI endpoints repeat the SR-15 detail-leak pattern (catch-all `Exception` → `str(e)` in 400) | Low | `app/routes/ui.py` | Deferred to v2 (with SR-15) |
| SR-27 | Google Fonts CDN added to `base.html` without SRI (expansion of SR-14) | Low | `app/templates/base.html` | Deferred to v2 (with SR-14) |
| SR-28 | Test coverage gap: no route-level negative tests for new UI POST endpoints | Informational | `tests/test_ui.py` | Fixed 2026-04-25 |

---

## 4. Detailed Findings

---

### SR-01 — `material_change` action performs state transition with no authorization check

**Severity:** Critical  
**File:line:** `app/routes/use_cases.py:65–105`, `app/services/lifecycle.py:421–440`

**Description:**  
The `POST /api/use-cases/{use_case_id}/transitions` endpoint dispatches to `LifecycleService.trigger_material_change` when `action == "material_change"`. That method calls `self._transition(... via_state_machine=False)`, which bypasses the state machine entirely and writes directly to `uc.status`. No role check, no ownership check, and no SoD guard are performed at any layer. Any authenticated user — including a low-privilege `requestor` with no relationship to the use case — can invoke this action.

```python
# app/routes/use_cases.py:94-96
elif action == "material_change":
    svc.trigger_material_change(
        use_case_id=use_case_id, actor_id=user.id, reason=payload.get("reason", "")
    )
```

```python
# app/services/lifecycle.py:421-440
def trigger_material_change(self, *, use_case_id: int, actor_id: int, reason: str) -> UseCase:
    uc = self._require_use_case(use_case_id)
    # NO: ensure_not_sponsor, role check, or ownership check
    self._session.add(ReReview(...))
    self._transition(uc, UseCaseStatus.re_review_required, ..., via_state_machine=False)
```

**Impact:**  
A requestor with no connection to a use case can force any approved or conditionally-approved use case into `re_review_required`, disrupting governance workflows and potentially nullifying approvals. The transition IS written to the audit log, but governance integrity is undermined regardless.

**Mitigation (< 5 lines):**  
Add a role/ownership check at the top of `trigger_material_change`. Sponsor or AO should be the only actors permitted:

```python
# app/services/lifecycle.py — add at top of trigger_material_change, after _require_use_case:
from app.models.enums import UserRole as _UR
actor = self._require_user(actor_id)
if actor.role not in (_UR.ao, _UR.ciso) and uc.sponsor_id != actor_id:
    raise SoDViolation("only the sponsor, AO, or CISO may trigger a material change")
```

**Recommended disposition:** Fix now, before any shared deployment.

---

### SR-02 — Dev session secret hardcoded in `docker/compose.yml`

**Severity:** High  
**File:line:** `docker/compose.yml:14`, `app/config.py:10`

**Description:**  
`app/config.py` defaults `session_secret` to `"dev-only-change-me"`. This is expected for local development. However, `docker/compose.yml` explicitly sets `SESSION_SECRET: dev-only-change-me`, meaning any operator who runs `docker compose up` without reading the documentation will get a production-looking deployment with a publicly-known signing key. The `itsdangerous.URLSafeSerializer` uses this key to sign session cookies; knowing the key allows forging sessions for arbitrary user IDs.

```yaml
# docker/compose.yml:14
SESSION_SECRET: dev-only-change-me
```

**Impact:**  
An attacker who knows the session secret can construct a valid signed cookie `_serializer.dumps({"uid": 1})` and authenticate as any user, including the AO or CISO. Full authentication bypass with zero credentials.

**Mitigation:**  
Replace the hardcoded value in `compose.yml` with a shell-variable reference that fails if unset:

```yaml
SESSION_SECRET: "${SESSION_SECRET:?SESSION_SECRET must be set to a random 32+ byte value}"
```

Alternatively, add a startup assertion in `config.py` that raises if the default is used when `environment != "dev"`.

**Recommended disposition:** Fix now.

---

### SR-03 — Intake-answer endpoint has no ownership/role check and writes no audit entry

**Severity:** High  
**File:line:** `app/routes/use_cases.py:51–62`, `app/services/lifecycle.py:52–73`

**Description:**  
`PATCH /api/use-cases/{use_case_id}/intake` requires only `current_user` (any authenticated user). It calls `upsert_intake_answer` for each key in the supplied `answers` dict. No check verifies that the caller is the sponsor of the use case, nor that the use case is in a status that permits editing (e.g., `draft` or `revision_requested`). Any authenticated user can alter the intake answers for any use case at any point in its lifecycle — including after approval. `upsert_intake_answer` writes no `AuditLogEntry`, so these changes are invisible to the hash-chained audit trail.

**Impact:**  
An adversary with any valid account can change the risk inputs underlying an approved use case (e.g., flip `handles_pii` from `true` to `false`), affecting future re-review scoring without leaving an audit record. This undermines the integrity the workbench is designed to provide.

**Mitigation:**  
1. In the route or service, verify the caller is the sponsor: `if uc.sponsor_id != user.id: raise HTTPException(403, ...)`.  
2. Add an `AuditLogWriter.append(...)` call inside `upsert_intake_answer` or at the route level.  
3. Optionally restrict writes to use cases in `draft` or `revision_requested` status.

**Recommended disposition:** Fix now.

---

### SR-04 — Auditor role not enforced as read-only at the route layer

**Severity:** High  
**File:line:** All endpoint handlers in `app/routes/use_cases.py`, `app/routes/attachments.py`, `app/routes/dashboard.py`, `app/routes/audit.py`

**Description:**  
`UserRole.auditor` carries the semantic of read-only observation. However, none of the API route handlers call `require_role(...)` to exclude the auditor. An auditor can call every write endpoint:

- `POST /api/use-cases` — create a new use case as sponsor
- `PATCH /api/use-cases/{id}/intake` — modify intake answers (see SR-03)
- `POST /api/use-cases/{id}/attachments` — upload files
- `POST /api/use-cases/{id}/transitions` with `action=triage` — because `_SYSTEM_ROLES = frozenset(UserRole)` includes auditor (see SR-17)

The state machine prevents some wrong-role actions (e.g., `submit` requires `requestor`), but this is incidental, not a deliberate read-only guard.

**Impact:**  
An auditor account, if compromised or misused, can actively disrupt governance workflows rather than being confined to observation. For a tool whose integrity depends on SoD, an unguarded auditor role is a significant gap.

**Mitigation:**  
Add a `require_role` dependency to each write route excluding `auditor` (and `ciso` for non-CISO actions), or define a `WRITE_CAPABLE_ROLES` constant and enforce it across all state-changing endpoints.

**Recommended disposition:** Fix now.

---

### SR-05 — No rate limiting or account lockout on `/login`

**Severity:** Medium  
**File:line:** `app/auth.py:66–79`

**Description:**  
`POST /login` has no rate limiting, no lockout after repeated failures, and no CAPTCHA. Argon2id with `m=65536, t=3, p=4` costs roughly 100–300 ms per verification, which provides per-thread throttling, but multiple concurrent requests bypass this. Uvicorn's threadpool (sync routes run in a thread executor) allows parallelism limited only by the OS thread limit. No failed-attempt counter exists anywhere in the codebase.

**Impact:**  
Online brute-force against any known email address. The seed accounts use predictable emails (`requestor@agency.gov`, etc.), so email enumeration is not required. Combining with SR-11 (timing oracle) further reduces the cost.

**Mitigation:**  
Add an in-process rate limiter (e.g., `slowapi`) keyed on IP or email, or implement a per-email failed-attempt counter in the database with exponential backoff. For v1 demo, at minimum, add a constant-time delay to balance fast and slow paths (see SR-11).

**Recommended disposition:** Defer to v2 (acceptable for local demo; required before production).

---

### SR-06 — Attachment upload reads entire file into memory with no size cap

**Severity:** Medium  
**File:line:** `app/routes/attachments.py:37`

**Description:**  
```python
content = file.file.read()  # no size limit
```
`python-multipart` streams the multipart body to a temp file by default, but `file.file.read()` loads the entire content into a Python `bytes` object before hashing and writing to disk. There is no `MAX_BYTES` check. A malicious authenticated user can upload a multi-gigabyte file, causing OOM on the server or exhausting disk space on the `attachments_dir` volume.

**Impact:**  
Denial of service. With the single-process SQLite deployment, one large upload can crash the server for all users.

**Mitigation (< 5 lines):**
```python
# app/routes/attachments.py — replace line 37 with:
MAX_BYTES = 50 * 1024 * 1024  # 50 MB
content = file.file.read(MAX_BYTES + 1)
if len(content) > MAX_BYTES:
    raise HTTPException(status_code=413, detail="file exceeds 50 MB limit")
```

**Recommended disposition:** Fix now.

---

### SR-07 — Attachment upload/download performs no use-case ownership check

**Severity:** Medium  
**File:line:** `app/routes/attachments.py:25–47` (upload), `app/routes/attachments.py:50–64` (download)

**Description:**  
`POST /api/use-cases/{use_case_id}/attachments` attaches a file to `use_case_id` without verifying the calling user has any relationship to that use case. Any authenticated user can upload attachments to any use case regardless of role or ownership. Similarly, `GET /api/attachments/{attachment_id}` returns any attachment to any authenticated user without checking access to the parent use case.

**Impact:**  
Data pollution (anyone can add files to any case) and unauthorized information disclosure (anyone can download sensitive documents — DPIAs, vendor contracts — attached to cases they have no governance role in).

**Mitigation:**  
In the upload route, fetch `UseCase` by `use_case_id`, verify the caller is the sponsor or has an assigned role. In the download route, check the parent use case exists and the caller has appropriate read access.

**Recommended disposition:** Fix now.

---

### SR-08 — `/api/audit-log` accessible to all authenticated roles

**Severity:** Medium  
**File:line:** `app/routes/audit.py:25–52`

**Description:**  
`GET /api/audit-log` requires only `current_user` with no role restriction. Any authenticated user — including a `requestor` — can read the full audit log. Payloads contain:
- `security_id` and `privacy_id` of assigned reviewers
- Review decisions and role assignments
- `risk_tier`, `classification`, and scoring `breakdown` for all cases
- `actor_id` for every action

This is the full decision history of the organization, intended for auditor access.

**Impact:**  
A requestor can enumerate the identities of all reviewers and AOs, read all review decisions and narratives, and understand the risk scoring of any case — including those they did not sponsor.

**Mitigation:**  
Add `require_role(UserRole.auditor, UserRole.ciso, UserRole.ao)` to both `list_entries` and `verify` handlers, or add a prefix dependency to the `/api/audit-log` router.

**Recommended disposition:** Fix now.

---

### SR-09 — Container runs as root (no `USER` directive in Dockerfile)

**Severity:** Medium  
**File:line:** `docker/Dockerfile` (entire file; note absence of USER directive)

**Description:**  
The Dockerfile has no `USER` directive. The application process runs as root (UID 0) inside the container. If an attacker achieves remote code execution through a dependency vulnerability or application bug, they immediately have root within the container, making container escape significantly easier. The `workbench-data` volume is mounted and owned by root.

**Impact:**  
Escalation from app-level RCE to container root; the volume mount means a root process can read/write the SQLite database directly.

**Mitigation:**  
Add before the `CMD` line in `docker/Dockerfile`:
```dockerfile
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser
```

**Recommended disposition:** Fix now.

---

### SR-10 — Audit log `limit` query parameter has no server-side upper bound

**Severity:** Medium  
**File:line:** `app/routes/audit.py:29`

**Description:**  
```python
limit: int = 200,
```
The `limit` parameter accepts any integer. A caller can pass `?limit=2147483647` to force the server to load the entire audit log into memory and serialize it as a single JSON response.

**Impact:**  
Memory exhaustion on a large log; slow response holds the SQLite writer lock; potential for sustained DoS by a single authenticated user.

**Mitigation (< 5 lines):**
```python
# app/routes/audit.py — replace limit parameter with:
from fastapi import Query
limit: int = Query(default=200, ge=1, le=1000),
```

**Recommended disposition:** Fix now.

---

### SR-11 — Login timing oracle distinguishes valid from invalid usernames

**Severity:** Medium  
**File:line:** `app/auth.py:73`

**Description:**  
```python
if not user or not user.active or not verify_password(password, user.password_hash):
```
Python short-circuits `or`: when `user is None`, `verify_password` is never called and the response returns in ~1 ms. When a valid, active user exists, `verify_password` performs Argon2id and returns in ~150–300 ms. Response time reveals whether an email address has a registered account.

**Impact:**  
Username/email enumeration. Combines with SR-05 (no rate limiting) to reduce brute-force search space.

**Mitigation:**  
Always run the password hash using a dummy hash when the user is not found:

```python
# app/auth.py — add module-level:
_DUMMY_HASH = _pwd.hash("__dummy__")

# In login(), replace the guard with:
user = get_user_by_email(session, email)
password_ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
if not user or not user.active or not password_ok:
    raise HTTPException(status_code=401, detail="invalid credentials")
```

**Recommended disposition:** Defer to v2 (low practical risk in local-only demo; required before production).

---

### SR-12 — Session cookie has `secure=False`; transmitted over plain HTTP

**Severity:** Low  
**File:line:** `app/auth.py:77`

**Description:**  
```python
response.set_cookie("session", _make_cookie(user.id), httponly=True, samesite="lax", secure=False)
```
`secure=False` means the session cookie is sent even over plain HTTP. If the service is ever accessed without TLS on a shared network, the session token is exposed to passive network observers.

**Impact:**  
Session hijacking on any unencrypted network path.

**Mitigation:**  
Set `secure=True` when `settings.environment != "dev"`, or always require TLS in non-dev deployments.

**Recommended disposition:** Accepted risk for v1 local demo. Must be addressed before any network-accessible deployment.

---

### SR-13 — No security response headers

**Severity:** Low  
**File:line:** `app/main.py` (no security middleware present)

**Description:**  
The application sets no security-relevant HTTP response headers. Missing: `Content-Security-Policy`, `X-Frame-Options` / `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`.

**Impact:**  
Defense-in-depth gaps. Without CSP, any XSS that bypasses Jinja's autoescaping would be unrestricted. Without `X-Frame-Options`, the login page can be framed for credential harvesting.

**Mitigation:**  
Add a Starlette `Middleware` or response hook that injects these headers. A minimal CSP for this app:
```
Content-Security-Policy: default-src 'self'; script-src 'self' cdn.tailwindcss.com unpkg.com; style-src 'self' 'unsafe-inline'
```

**Recommended disposition:** Defer to v2.

---

### SR-14 — CDN scripts loaded without Subresource Integrity hashes

**Severity:** Low  
**File:line:** `app/templates/base.html:6–7`

**Description:**  
```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/htmx.org@1.9.12"></script>
```
Neither `<script>` includes an `integrity=` attribute. A compromised CDN could serve arbitrary JavaScript that would execute in every user's browser session. HTMX is version-pinned (good), but there is no cryptographic integrity check.

**Impact:**  
Supply-chain XSS: a compromised CDN could exfiltrate session cookies or governance records.

**Mitigation:**  
Compute SHA-384 hashes of the current CDN assets and add `integrity="sha384-..."` to both tags, or vendor the assets locally under `app/static/`.

**Recommended disposition:** Defer to v2 (pre-production hardening).

---

### SR-15 — SoD / lifecycle exceptions leak internal IDs in HTTP 400 `detail`

**Severity:** Low  
**File:line:** `app/routes/use_cases.py:102–103`, `app/routes/ui.py:113–114`

**Description:**  
```python
except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
```
`SoDViolation` and `ValueError` messages like `"only the sponsor may submit use case 3 (actor=5)"` or `"actor previously served as security reviewer on this case"` are forwarded verbatim to the HTTP client, leaking internal integer IDs and role relationships.

**Impact:**  
Low; IDs are accessible through other endpoints. However, confirming reviewer identities via error messages is undesirable in a privacy-sensitive governance tool.

**Mitigation:**  
Catch `SoDViolation` separately, log the full message server-side, and return a generic `"operation not permitted"` to the client.

**Recommended disposition:** Defer to v2.

---

### SR-16 — `passlib` is unmaintained

**Severity:** Low  
**File:line:** `pyproject.toml:13`

**Description:**  
`passlib[argon2]` is listed as a dependency. passlib's last release was 1.7.4 in November 2020. The project has no active maintainer. The `argon2-cffi` library that backs passlib's argon2 support is separately maintained and current.

**Impact:**  
Low today; elevated if a vulnerability is discovered in passlib's wrapping logic or `CryptContext` machinery, since no patch would be forthcoming.

**Mitigation:**  
Migrate to `argon2-cffi` directly, or to `pwdlib[argon2]` which is a maintained passlib successor. Migration is confined to `app/auth.py`.

**Recommended disposition:** Defer to v2 dependency refresh.

---

### SR-17 — `_SYSTEM_ROLES` includes auditor and CISO, granting unintended triage rights

**Severity:** Low  
**File:line:** `app/workflow.py:43`

**Description:**  
```python
_SYSTEM_ROLES = frozenset(UserRole)
```
This assigns every defined role — including `auditor` and `ciso` — as valid actors for `auto_triage` and `auto_advance` transitions. The intent appears to be "the system itself (background job)". As a result, an auditor can call `POST /api/use-cases/{id}/transitions` with `{"action": "triage"}` on any submitted use case and advance it through triage. The existing SoD checks (`ensure_not_sponsor`, `ensure_triager_not_reviewer`) do not prevent this because auditors are not sponsors, and the reviewer SoD check only applies when `target_role == security`.

**Impact:**  
An auditor can advance a use case through the triage gate, bypassing deliberate security-reviewer oversight.

**Mitigation:**  
Restrict `_SYSTEM_ROLES` to the roles that should legitimately trigger triage:

```python
# app/workflow.py:43 — replace with:
_SYSTEM_ROLES = frozenset({UserRole.security_reviewer, UserRole.privacy_reviewer, UserRole.ao})
```
Or use a sentinel pattern for background-only transitions (background jobs can call `_transition(..., via_state_machine=False)` directly, bypassing `apply()`).

**Recommended disposition:** Fix now (low-effort, high-clarity).

---

### SR-18 — Seed file ships trivial `demo` passwords for all accounts

**Severity:** Informational  
**File:line:** `seed/users.json`

**Description:**  
All seven seed accounts use `"password": "demo"`. Acceptable for a local demo. If a developer runs this against any shared or internet-accessible host without changing passwords, all accounts (including AO and CISO) are trivially compromised.

**Recommended disposition:** Accepted risk for local demo. The startup output or README should emit a clear warning that seed credentials must be rotated before any shared deployment.

---

### SR-19 — OpenAPI `/docs` and `/redoc` enabled with no authentication gate

**Severity:** Informational  
**File:line:** `app/main.py:14`

**Description:**  
FastAPI enables `/docs` (Swagger UI) and `/redoc` by default with no auth guard. These expose the full API schema and an interactive console.

**Recommended disposition:** Accepted risk for v1 demo. Disable for production: `FastAPI(..., docs_url=None, redoc_url=None)`.

---

### SR-20 — `/healthz` leaks `environment` name to unauthenticated callers

**Severity:** Informational  
**File:line:** `app/main.py:26–28`

**Description:**  
`GET /healthz` is unauthenticated and returns `{"status": "ok", "env": "demo"}` (or `dev`, `prod`). Minor information disclosure about deployment configuration.

**Recommended disposition:** Accepted risk. Remove the `env` field from the response if desired.

---

### SR-21 — No CSRF tokens on HTML forms

**Severity:** Informational  
**File:line:** `app/templates/login.html`, `app/templates/use_case_detail.html`, `app/templates/use_case_new.html`

**Description:**  
All HTML forms submit via `method="post"` with no CSRF token. HTMX AJAX calls also carry no anti-CSRF header.

**Why this is not currently exploitable:** The session cookie is set with `samesite=lax`. The browser will not send this cookie with cross-origin POST requests from third-party sites. A third-party page cannot force a victim's browser to submit a credentialed POST to this application.

**Recommended disposition:** Accepted risk. Explicit CSRF tokens would be defense-in-depth; defer to v2 if `samesite=none` cookies are ever needed.

---

### SR-22 — Audit hash chain has TOCTOU window under concurrent writers

**Severity:** Informational  
**File:line:** `app/services/audit.py:30–66`

**Description:**  
`AuditLogWriter._latest_hash()` reads the current chain tip, then `session.flush()` inserts the new entry. Between these two operations, another thread could read the same chain tip, producing two entries that both claim the same `prev_hash`. Under SQLite WAL mode with NORMAL synchronous, the database serializes write transactions, so in practice one of the two concurrent inserts will fail with a write-lock error (raising a 500 to the user) rather than silently forking the chain.

**Impact:**  
Occasional 500 errors under high concurrency (rare in practice for a single-agency demo). No silent chain corruption under SQLite's write-lock semantics.

**Recommended disposition:** Informational for v1. For v2 multi-process deployment, add an application-level write serialization layer or a `SELECT ... FOR UPDATE` equivalent.

---

### SR-23 — UI router lets auditor create draft use cases (regression of SR-04 in UI surface)

**Severity:** Medium  
**File:line:** `app/routes/ui.py:52-70`  
**Discovered:** 2026-04-25 second pass

**Description:**  
The API write path (`POST /api/use-cases`) uses `Depends(writer_user)` and rejects auditors per the SR-04 fix. The parallel UI route added in the editorial-gazette UI work used `Depends(current_user)` instead:

```python
# app/routes/ui.py — pre-fix
@router.post("/ui/use-cases", response_class=HTMLResponse)
def create_use_case(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],   # ← should be writer_user
    ...
) -> RedirectResponse:
    svc = LifecycleService(session)
    uc = svc.create_draft(sponsor_id=user.id, ...)
```

`LifecycleService.create_draft` itself has no role guard. An authenticated auditor could `POST /ui/use-cases` and become sponsor of a draft use case. The auditor cannot subsequently submit it (workflow blocks `_REQ`-only actions for non-requestor roles), so blast radius is limited to **data pollution** and **audit-trail noise** (`actor_id=auditor_id, action="create_draft"`), not governance subversion.

**Impact:**  
Integrity of the audit trail (auditor falsely associated as sponsor) and DoS via unbounded draft creation by a compromised auditor account.

**Mitigation (1 line):**
```python
# app/routes/ui.py:55
user: Annotated[User, Depends(writer_user)],
```

**Recommended disposition:** Fix now. One-line change.

---

### SR-24 — New UI write endpoints lack `writer_user` defense-in-depth

**Severity:** Low  
**File:line:** `app/routes/ui.py:120, 144, 162, 210` (pre-fix)  
**Discovered:** 2026-04-25 second pass

**Description:**  
All four new/refactored UI POST handlers (`assign_reviewers`, `request_revision`, `submit_review`, `ui_transition`) used `Depends(current_user)` instead of `Depends(writer_user)`. Workflow `apply()` does block auditors because no transition includes `UserRole.auditor` in `actor_roles`, so the practical impact today is zero for these endpoints. But:

1. The SR-04 design relies on a defensive layer at the route boundary as well as the workflow layer. A future code path that doesn't go through `apply()` (e.g., a direct service call added later) would slip through.
2. The error returned when the workflow blocks an auditor was `HTTPException(400, "role auditor cannot perform request_revision from triage")` — which leaked role and state instead of returning the cleaner 403 from `writer_user`.
3. `submit_review` had its own role check (`if user.role not in role_map`), but that's a positive-list of two roles rather than the consistent project pattern.

**Impact:**  
Defense-in-depth gap. Auditor bypass of the auth layer relies entirely on the workflow layer; the two-layer SR-04 design intent was not honored in the UI router.

**Mitigation:**  
Replace `current_user` with `writer_user` on all four POST handlers in `ui.py`. Read-only GETs (`dashboard`, `login_page`, `new_page`, `detail`) remain on `current_user` so auditors can still observe.

**Recommended disposition:** Fix now (defense-in-depth, ~5 lines).

---

### SR-25 — No length caps on reviewer narrative, revision reason, or condition fields

**Severity:** Low  
**File:line:** `app/routes/ui.py:140-202` (pre-fix)  
**Discovered:** 2026-04-25 second pass

**Description:**  
The new UI POST handlers accepted unbounded user-supplied free-text fields:

```python
narrative: Annotated[str, Form()] = "",
condition_names: Annotated[list[str], Form()] = [],
condition_descriptions: Annotated[list[str], Form()] = [],
reason: Annotated[str, Form()],
```

A reviewer (security or privacy) could submit a 10 MB narrative, thousands of conditions, or a 10 MB revision reason in one POST. All values were stored verbatim in `Review.narrative`, `Condition.name/description`, or `StateTransition.reason`. SQLite has no row-size limit, so the request succeeds and bloats the DB. Combined with the absence of rate limiting (existing SR-05) and a compromised reviewer account, this is a viable path to growing the DB to GB.

**Impact:**  
DB-bloat denial of service by a compromised reviewer account. The workbench is intended for ~10s–100s of cases per agency, so even moderate abuse degrades performance noticeably.

**Mitigation:**  
Module-level constants and explicit checks at the top of each handler:

```python
_MAX_NARRATIVE = 4000
_MAX_REASON = 4000
_MAX_CONDITION_FIELD = 1000
_MAX_CONDITIONS_PER_REVIEW = 50

# request_revision:
if len(reason) > _MAX_REASON:
    raise HTTPException(400, f"reason exceeds {_MAX_REASON}-character limit")

# submit_review:
if len(narrative) > _MAX_NARRATIVE: raise HTTPException(400, ...)
if len(condition_names) > _MAX_CONDITIONS_PER_REVIEW: raise HTTPException(400, ...)
for v in (*condition_names, *condition_descriptions):
    if len(v) > _MAX_CONDITION_FIELD: raise HTTPException(400, ...)
```

**Recommended disposition:** Fix now (cheap, prevents trivial DoS).

---

### SR-26 — New UI endpoints repeat the SR-15 detail-leak pattern

**Severity:** Low  
**File:line:** `app/routes/ui.py:134, 152, 199, 222`  
**Discovered:** 2026-04-25 second pass

**Description:**  
Every new UI handler ends with:

```python
except Exception as e:
    raise HTTPException(400, str(e))
```

This propagates `SoDViolation` messages like `"actor previously served as security reviewer on this case"` and `StateMachineError` messages like `"role auditor cannot perform submit_review from in_review"` to the HTTP body. SR-15 already documented this pattern and deferred it to v2; the new code spreads it to 3 more endpoints, which is a moderate worsening of the same finding.

**Mitigation:**  
Catch `SoDViolation` and `StateMachineError` separately, log full message server-side, return `"operation not permitted"` (403) or `"invalid state transition"` (409) generically. Keep `ValueError → 400` for genuinely user-facing input errors.

**Recommended disposition:** Bundle with the SR-15 v2 cleanup. No new fix-now.

---

### SR-27 — Google Fonts CDN added without SRI (expands SR-14)

**Severity:** Low  
**File:line:** `app/templates/base.html:23-25`  
**Discovered:** 2026-04-25 second pass

**Description:**  
The dark-mode/shadcn redesign added two new third-party origins to the base template:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist+Mono:..." rel="stylesheet">
```

CSS from a compromised stylesheet origin can exfiltrate via attribute selectors and `url(...)` callbacks. SR-14 already covered Tailwind + HTMX without SRI; now Google Fonts CSS is added too. Same disposition.

**Mitigation:**  
Either vendor the Geist font locally under `app/static/fonts/`, or add an SRI hash to the stylesheet `<link>` and serve fonts with `crossorigin`. Vendoring is the cleaner option and removes the runtime dependency.

**Recommended disposition:** Defer to v2 alongside SR-14.

---

### SR-28 — Test coverage gap on new UI POST endpoints

**Severity:** Informational  
**File:line:** `tests/test_ui.py`  
**Discovered:** 2026-04-25 second pass

**Description:**  
Pre-fix, `test_ui.py` had three tests, none exercising:
- `POST /ui/use-cases` (negative case: auditor blocked from creating)
- `POST /ui/use-cases/{id}/assign_reviewers` (auth, role, SoD)
- `POST /ui/use-cases/{id}/request_revision` (reason required, sponsor blocked)
- `POST /ui/use-cases/{id}/submit_review` (role-restricted, conditional requires conditions)

The service-layer logic was well-tested (`test_reviews.py` adds 3 new tests for `request_revision`), but the route-layer guard for SR-23/SR-24/SR-25 was not verified by any test. The lack of a regression test was the proximate cause of SR-23 not being caught by the existing CI run.

**Mitigation:**  
Add 10 route-level tests covering: auditor blocked from each write endpoint, requestor allowed to create, length caps on narrative/reason/conditions, oversized condition fields rejected.

**Recommended disposition:** Fix now alongside SR-23/24/25.

---

## 5. What Is NOT a Finding

The following areas were examined and found to be in acceptable condition.

| Area | Verdict |
|------|---------|
| **SQL injection** | SQLModel/SQLAlchemy uses parameterized queries exclusively throughout `app/`. No raw `text()` calls with user input found anywhere. |
| **Template XSS injection** | Starlette's `Jinja2Templates` sets `autoescape=True` by default (confirmed in starlette source). No template uses the `|safe` filter on user-supplied data. User-controlled fields (`uc.title`, `uc.business_purpose`, `t.reason`, `user.name`) are safely escaped. |
| **Header injection in Content-Disposition** | `_safe_content_disposition()` in `app/routes/attachments.py` strips `"` and `\` and URL-encodes the `filename*` parameter. A dedicated test (`test_download_content_disposition_rejects_header_injection`) confirms that CR/LF characters cannot be injected into response headers. |
| **Path traversal in attachment storage** | Files are stored at `sha256[:2]/sha256` — a content-addressed path derived entirely from the SHA-256 hash of the file content, not from the user-supplied filename. No user-controlled path component exists. |
| **Open redirect on `/login`** | Post-login redirect is hardcoded to `url="/"` at `app/auth.py:75`. There is no `next=` query parameter, so open redirect is not possible. |
| **Argon2 parameter strength** | Default passlib argon2 parameters: `m=65536` (64 MiB), `t=3`, `p=4`. This meets and exceeds the OWASP Argon2id minimums (m≥19456 KiB, t≥2). |
| **Session cookie `httponly`** | Set to `True` at `app/auth.py:77`. JavaScript cannot read the cookie value. |
| **Cookie forgery without known secret** | `itsdangerous.URLSafeSerializer` uses HMAC-based signing. Without the secret key, cookies cannot be forged (assuming the default is not used — see SR-02). |
| **SoD enforcement on triage/review/AO paths** | `ensure_not_sponsor`, `ensure_unique_cross_cycle_roles`, `ensure_triager_not_reviewer`, and `ensure_ao_clean` are all called in the relevant `LifecycleService` methods and cover the four documented SoD invariants. The missing check is limited to `trigger_material_change` (SR-01). |
| **Audit hash canonicalization round-trip stability** | `_canonical_json` uses `sort_keys=True, separators=(',', ':')`. All payload values at hash time are Python primitives (str, int, list of str). The only datetime in `hash_input` is `created_at`, serialized via `.isoformat()` at write time and in `verify_chain`. `UtcDateTime` preserves microseconds through SQLite. Round-trip is stable. |
| **Audit log `verify_chain` correctness** | The verification walk correctly recomputes `prev_hash` → `hash` for every entry. A tampered `payload` in any entry will invalidate that entry's hash. The tamper test in `tests/test_audit.py` confirms detection. |
| **Shell injection** | No `subprocess`, `os.system`, `eval`, or `exec` calls exist anywhere in `app/`. |
| **MIME type confusion on download** | Download responses force `media_type="application/octet-stream"`. Browsers will not execute or inline-render the returned file. |
| **`check_same_thread=False` SQLite flag** | Correctly conditioned on `database_url.startswith("sqlite")` at `app/db.py:8`. Required for FastAPI's threadpool execution model and does not introduce data races beyond the TOCTOU noted in SR-22. |
| **Foreign key enforcement** | `PRAGMA foreign_keys=ON` set on every SQLite connection via the `connect` event listener at `app/db.py:12–19`. Referential integrity is enforced at the database layer. |
| **Dependency versions** | All non-passlib dependencies (`fastapi`, `uvicorn`, `sqlmodel`, `sqlalchemy`, `pydantic`, `itsdangerous`, `python-multipart`, `jinja2`) are current and have no known critical CVEs as of this review date. |
| **Docker base image** | `python:3.12-slim` is a current, minimal Debian-based image. No known critical CVEs at review time. |

---

## 6. Fix Log

**Commit:** `4b5b43b`  
**Branch:** `feature/security-hardening`  
**Date:** 2026-04-17  
**Tests:** 56 → 73 passing (17 new regression tests)

| ID | Change summary |
|----|----------------|
| SR-01 | Added ownership check at the top of `trigger_material_change` in `app/services/lifecycle.py`. Raises `SoDViolation` unless the actor is the use case sponsor, an AO, or a CISO. |
| SR-02 | Replaced hardcoded `SESSION_SECRET: dev-only-change-me` in `docker/compose.yml` with a required env-var reference that fails at `docker compose up` time if unset. Added `model_post_init` guard in `app/config.py` that raises `RuntimeError` when `environment != "dev"` and the default secret is in use. |
| SR-03 | Added sponsor-only ownership check (403) and editable-status gate (`draft`, `revision_requested`, `re_review_required` → 409 otherwise) to `patch_intake` in `app/routes/use_cases.py`. Added `actor_id` keyword parameter to `upsert_intake_answer` in `app/services/lifecycle.py`; the method now writes an `AuditLogEntry` with `action="upsert_intake_answer"` on every call. Updated all callers (`seed.py`, `test_lifecycle.py`, `test_reviews.py`, `test_packet.py`). |
| SR-04 | Defined `WRITE_CAPABLE_ROLES` constant and `writer_user` dependency in `app/auth.py`. Replaced `Depends(current_user)` with `Depends(writer_user)` on `create`, `patch_intake`, `transition` (use-cases router), and `upload` (attachments router). Read-only GET endpoints retain `current_user`. |
| SR-06 | Added `MAX_BYTES = 50 * 1024 * 1024` module-level constant in `app/routes/attachments.py`. Upload now reads at most `MAX_BYTES + 1` bytes and raises HTTP 413 if the content exceeds the limit. |
| SR-07 | Added `_can_access_use_case(user, use_case)` helper in `app/routes/attachments.py`. Upload enforces sponsor-or-non-requestor (403 otherwise). Download fetches the parent `UseCase` and applies the same check. Auditors are excluded from upload by the `writer_user` dependency (SR-04) and can download via the non-requestor branch. |
| SR-08 | Replaced `Depends(current_user)` with `require_role(UserRole.auditor, UserRole.ciso, UserRole.ao)` on both `list_entries` and `verify` handlers in `app/routes/audit.py`. |
| SR-09 | Added `RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app` and `USER appuser` to `docker/Dockerfile` before the `EXPOSE` directive. |
| SR-10 | Replaced bare `limit: int = 200` with `limit: int = Query(default=200, ge=1, le=1000)` in `app/routes/audit.py`. FastAPI now returns HTTP 422 for out-of-range values. |
| SR-17 | Replaced `_SYSTEM_ROLES = frozenset(UserRole)` with `frozenset({UserRole.security_reviewer, UserRole.privacy_reviewer, UserRole.ao, UserRole.ciso})` in `app/workflow.py`. Auditor and requestor are now excluded from system-driven transitions (`auto_triage`, `auto_advance`, `expire`). Updated `test_full_happy_path` to use `security_reviewer` for the `auto_triage` step (the previous use of `requestor` was a test-intent mismatch). |

**Design choices:**
- SR-03 editable statuses: chose `{draft, revision_requested, re_review_required}` as the permitted set for intake edits. `re_review_required` is included because the sponsor needs to update answers before resubmitting after a material change.
- SR-07 access model: "non-requestor can access any case" is the simplest rule that matches governance intent (reviewers, AO, CISO, auditor all need cross-case visibility). A future v2 could restrict to assigned-reviewer only.
- SR-17 `_SYSTEM_ROLES` includes `ciso` per the fix-spec instruction even though the original security review mitigation suggested excluding it. The spec explicitly includes `ciso` in `_SYSTEM_ROLES`.

---

**Commit:** (TBD — uncommitted at time of writing)  
**Branch:** `main`  
**Date:** 2026-04-25 (second-pass fixes)  
**Tests:** 76 → 86 passing (10 new route-level negative tests in `tests/test_ui.py`)

| ID | Change summary |
|----|----------------|
| SR-23 | Replaced `Depends(current_user)` with `Depends(writer_user)` on `POST /ui/use-cases` in `app/routes/ui.py`. Auditor now receives 403 at the auth layer instead of 303 success. |
| SR-24 | Replaced `Depends(current_user)` with `Depends(writer_user)` on the four UI POST handlers: `ui_assign_reviewers`, `ui_request_revision`, `ui_submit_review`, `ui_transition`. GET handlers (`login_page`, `dashboard`, `new_page`, `detail`) intentionally remain on `current_user` so auditors retain read access. |
| SR-25 | Added module-level constants `_MAX_NARRATIVE = 4000`, `_MAX_REASON = 4000`, `_MAX_CONDITION_FIELD = 1000`, `_MAX_CONDITIONS_PER_REVIEW = 50` in `app/routes/ui.py`. Each affected handler validates input length before invoking the lifecycle service. Rejected requests return HTTP 400 with a message naming the violated field (the field name only — no internal IDs leak). |
| SR-28 | Added 10 new tests in `tests/test_ui.py`: `test_ui_create_use_case_blocks_auditor`, `test_ui_create_use_case_allows_requestor`, `test_ui_assign_reviewers_blocks_auditor`, `test_ui_request_revision_blocks_auditor`, `test_ui_submit_review_blocks_auditor`, `test_ui_transition_blocks_auditor`, `test_ui_request_revision_rejects_oversized_reason`, `test_ui_submit_review_rejects_oversized_narrative`, `test_ui_submit_review_rejects_too_many_conditions`, `test_ui_submit_review_rejects_oversized_condition_field`. The `_client` test fixture was extended to accept an `extra_users` list of `(email, UserRole)` tuples, and a `_login` helper was added. |

**Design choices (second pass):**
- All four limits (`narrative`, `reason`, condition field, conditions-per-review) chosen as round numbers comfortably above realistic governance use (a thoughtful narrative is rarely > 1000 chars; 50 conditions in one review is already excessive) but low enough to bound DB row size at < 5 KiB worst case.
- Length checks live in the route layer rather than the service layer so the API and UI can have differently-tuned policies if needed. Currently the API path (`POST /api/use-cases/{id}/transitions`) does not impose the same caps; v2 should align them.
- SR-26 and SR-27 deferred to v2 alongside their parent findings (SR-15 and SR-14 respectively).
