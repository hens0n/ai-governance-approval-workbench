# AI Governance Review and Approval Workbench

A lightweight internal platform that manages intake, review, approval, and monitoring of proposed AI use cases in a regulated organization.

**Start here:**
- [**Demo walkthrough**](docs/DEMO.md) — screenshots, seeded credentials, and a 3-minute demo script
- [**Lessons learned + extension roadmap**](docs/lessons-learned.md) — what worked, what surprised, where it goes next
- [Scoping brief](docs/superpowers/specs/2026-04-17-ai-governance-workbench-scoping.md) — problem statement, stakeholders, requirements, assumptions, risks
- [Design spec](docs/superpowers/specs/2026-04-17-ai-governance-workbench-design.md) — architecture, data model, state machine, control mappings
- [Implementation plan](docs/superpowers/plans/2026-04-18-ai-governance-workbench.md) — the 16-task TDD plan
- [Sample decision packet](docs/sample-decision-packet.md) — generated Markdown output for a high-risk use case

## Features

- **Use case lifecycle** — state machine in `app/workflow.py`: draft → submitted → triage → in_review → AO decision → approved / conditionally approved / rejected, with revision, withdrawal, expiration, and revocation paths
- **Risk scoring & control mapping** — versioned rubric and control template JSON in `app/policy/` drive automated risk tier and required mitigations
- **Separation of duties** — enforced in `app/services/sod.py`; the same actor cannot review and approve
- **Tamper-evident audit log** — every state change is hash-chained. `GET /api/audit-log` lists entries and `GET /api/audit-log/verify` reports the first broken link (auditor / CISO / AO only)
- **File attachments** — `POST /api/use-cases/{id}/attachments` (max 50 MB) and `GET /api/attachments/{id}`, with role-scoped access
- **Post-approval re-review** — three triggers (`scheduled`, `material_change`, `policy_change`) open a `ReReview` record and require resubmission; expose via `POST /api/use-cases/{id}/transition` with `action: material_change`
- **Decision packet** — Markdown packet generated from use case, scores, controls, and reviewer notes (see `docs/sample-decision-packet.md`)

## Quickstart (demo)

```bash
make demo
# visit http://localhost:8000/login
# log in as any seeded user (password: demo):
#   requestor@agency.gov     # role: requestor
#   triager@agency.gov       # role: security_reviewer (triages new submissions)
#   security@agency.gov      # role: security_reviewer
#   privacy@agency.gov       # role: privacy_reviewer
#   ao@agency.gov            # role: ao (authorizing official)
#   ciso@agency.gov          # role: ciso
#   auditor@agency.gov       # role: auditor (read-only + audit log access)
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
