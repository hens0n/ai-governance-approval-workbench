# Lessons Learned and Extension Roadmap

Reflections from building v1 of the AI Governance Review and Approval Workbench, and where it would go next in a real engagement.

## What worked well

**Spec-first, plan-second, code-third.** The scoping brief produced the artifacts that got the hardest arguments out of the way — who the stakeholders are, what "good" looks like operationally, what's out of scope. The design spec turned that into a shape of a system. The implementation plan turned that shape into 16 discrete TDD tasks, each with verbatim code blocks and passing tests. By the time any code was written, every consequential decision was already in a document that could be challenged by a reviewer. This is deliberate; it's how you move fast without moving recklessly in regulated environments.

**SoD enforced in the service layer, not the UI.** The guard functions live in `app/services/sod.py` and are called from every state-changing method on `LifecycleService`. The HTTP routes are defense-in-depth. A reviewer who bypasses the UI by hitting the API directly hits the same check. Tests verify both paths. Auditors should be able to state the SoD invariants in English and find them enforced at one point in the code — that's what `sod.py` is.

**Hash-chained audit log as a real primitive, not decoration.** Every state change, every review submission, every condition update writes a row with `hash = sha256(prev_hash || canonical_json(payload))`. A `verify_chain` function walks the log in order and detects both broken linkage and mutated payloads. Tests tamper with a row and confirm verification fails deterministically. This is the kind of thing agencies ask about in an assessment; having it already built and tested is a different conversation than promising to build it.

**The state machine is one file.** `app/workflow.py` has 20 transitions in a single `_TRANSITIONS` tuple. Any reviewer can read the whole workflow end-to-end without grepping. This was an explicit design call — library magic hides invariants, and hidden invariants are how governance tools fail their own thesis.

## What surprised me

**Python 3 + SQLite + UTC is a trap.** The spec called for timezone-aware `datetime` fields, the tests asserted `tzinfo is timezone.utc` after a roundtrip, and SQLite silently strips tz info. The implementer caught it, added an `UtcDateTime` TypeDecorator, and wired it onto every datetime column. A good reminder that the plan's "verbatim code" shouldn't be followed into a wall — the spirit of the spec was UTC-preserving, not "paste this code verbatim even if the test fails."

**FastAPI `Depends` captures references at route definition.** The plan's auth test used `monkeypatch.setattr(auth_mod, "get_session", ...)` to swap the session dependency. This is the Pythonic way, but FastAPI's `Depends(get_session)` captured the function reference at route definition time, so the monkeypatch was invisible to the routes. The fix — `app.dependency_overrides[get_session] = ...` — is documented in FastAPI's docs but only if you go looking. This is the kind of thing that looks like a test bug and is actually a framework behavior.

**Reviews that care about *why* catch more than reviews that care about *what*.** Spec-compliance reviews confirmed the code matched the plan verbatim. Code-quality reviews caught real issues: an `UtcDateTime` applied inconsistently on optional fields, `_read_cookie` catching too narrow an exception set, egg-info files committed by accident. A review that doesn't change behavior is worth less than one that does.

## What I would do differently next time

**Ship the policy template as data from day one, not "v2."** v1 hardcodes the rubric and control template as JSON files in the repo. A real agency will want to edit these through the UI with an approval workflow of their own. Ironically, a governance workbench that doesn't govern its own policy template is doing the thing the scoping brief warns about (R-08 reflexivity). Next version: treat `policy_template` as a first-class entity with its own workflow.

**Write end-to-end integration tests earlier.** Per-service tests caught their own units' bugs but missed at least one integration seam: a stray `data/` directory from a manual smoke run poisoned the `pip install -e .` discovery. An end-to-end test that installed the package from a clean checkout would have caught this. Deferred to v1's "Known Gaps" — would move to v1 on a do-over.

**Log as a first-class concern, not an afterthought.** The audit log covers *what* happened. But a demo operator watching the server stream has no way to see *what's happening right now* — there's no structured logging. In a real deployment this is how the oncall engineer diagnoses the "why is this review stuck in `InReview`" ticket. It would have cost one small task to wire `structlog` and emit an event on every state transition; worth doing.

**Document the deviations inline.** Each of the three non-verbatim deviations (UtcDateTime, dependency_overrides, Starlette 1.0 TemplateResponse) was explained in the subagent's report and in my code review, but there's no central "here's what differs from the plan, and why" in the repo itself. Future contributors will rediscover them. Next time: add a `docs/deviations.md` or keep the plan file live-edited with strike-through.

## Extension roadmap

These are the coherent v2 increments, ordered by what I'd tackle first:

**Tier 1 — close the v1 gaps.** Each of these is 1-2 TDD tasks and unlocks visible value.

- **Attachment upload + download.** Content-addressed filesystem, SHA-256 on write, mapped to the already-existing `attachment` table. Demo impact: reviewers can attach DPIAs and vendor contracts to conditions.
- **Decision packet REST route.** Wrap `generate_markdown_packet` as `POST /api/use-cases/{id}/packet` and `GET /api/use-cases/{id}/packet?fmt=md|pdf`. Ship Markdown first; PDF via WeasyPrint as opt-in.
- **End-to-end happy-path integration test.** One pytest that drives the full workflow through the API: create → submit → triage → both reviews → approve-with-conditions → packet. Any future regression shows up here first.
- **Alembic migrations.** v1 uses `SQLModel.metadata.create_all`. Production needs migrations; set this up before the schema drifts.

**Tier 2 — production readiness.**

- **Enterprise identity.** SAML/OIDC SSO; SCIM for provisioning; drop local accounts to break-glass-only.
- **Persistent object storage.** S3-compatible backend behind the `BlobStore` seam; versioning enabled; lifecycle policy for attachments.
- **Observability.** Structured logging, request tracing, metrics on time-to-decision and conditional-approval rate. Dashboards for the CISO.
- **Audit log attestation.** Nightly job that exports the chain head to an external WORM bucket with a signed timestamp. Weekly external re-verification. The mitigation in the scoping brief's R-06.

**Tier 3 — agency-specific depth.**

- **Policy template as a managed entity** with its own workflow (see "what I'd do differently").
- **Continuous monitoring hooks** — drift, accuracy decay, bias drift — wired back into the workbench as a "material change" trigger.
- **Vendor risk integration.** Intake answers cross-reference a vendor risk database; vendors with outstanding issues block submission until resolved.
- **Multi-tenant** — one instance, many agencies or components, with shared policy templates and isolated decision logs.

**Tier 4 — speculative and ambitious.**

- **Automated discovery.** Pull from a cloud asset inventory to surface AI usage the workbench hasn't captured yet. Shadow AI detection, not enforcement.
- **Enforcement coupling** — wire approved/rejected status into an API gateway so denied use cases actually can't invoke their model. This is where a governance workbench stops being advisory and becomes a control point. That transition is a bigger conversation than any feature.

## The story to tell an interviewer

A CISO hiring a cyber-risk-and-governance lead doesn't care whether the test suite has 51 tests or 510. They care whether the candidate can take a policy that exists and turn it into a workflow that works. This project is the artifact that says I can do that: here is the scoping brief, here is the risk rubric mapped to real controls, here is the state machine a reviewer can read top-to-bottom, here is the audit log that holds up in a post-incident conversation. The code is the proof, not the point.
