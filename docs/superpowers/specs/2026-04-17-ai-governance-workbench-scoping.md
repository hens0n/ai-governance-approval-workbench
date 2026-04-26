# AI Governance Review and Approval Workbench — Scoping Brief

**Date:** 2026-04-17
**Status:** Scoping (pre-design)
**Author:** Jacob Henson
**Source idea:** `idea.md`
**Regulatory frame:** Federal civilian / FISMA Moderate baseline (illustrative; the workbench is regime-agnostic by design)

---

## 1. Problem Statement

Federal agencies are being asked to adopt copilots, LLM APIs, and agentic workflows on a timeline that outpaces their ability to govern them. OMB M-24-10 and the agency AI use case inventory requirement assume a process exists; in practice, most components are still answering AI requests through ad-hoc email threads, one-off ATO conversations, and the judgment of whoever picks up the phone. Policy documents exist. An operational workflow does not.

The cost of the gap is not theoretical. Shadow AI proliferates because the legitimate path is unclear. Approvals are inconsistent because there is no shared rubric. Audit findings land because decisions cannot be reconstructed. And when something goes wrong — a model leaking CUI, a vendor changing terms, a use case drifting beyond its original scope — there is no record of who authorized what, against which controls, with what conditions.

"Good" looks operationally simple: every proposed AI use case enters a single intake, is scored against a published rubric, routed to the right reviewers, decided with conditions attached, and re-reviewed on a known cadence. Every state change is logged. Every decision is downloadable. The workbench is the place where AI governance stops being a memo and starts being a workflow.

---

## 2. Stakeholder Map

| Role | What they need from the system | What they fear | Decision authority |
|---|---|---|---|
| **CISO / AI Governance Lead** | Portfolio view of all AI use cases, risk distribution, approval throughput, expiring reviews | Surprise at a hearing or in an IG report; an AI incident traced to an unreviewed use case | Sets policy; final authority on high-risk approvals |
| **Privacy / Compliance Reviewer** | Structured intake with data classification answers; ability to attach conditions; clear handoff from security review | Approving something that turns out to involve PII or CUI they didn't see; being scapegoated for an incomplete intake | Concur / non-concur on privacy-impacting use cases |
| **Security Reviewer (ISSO/ISSM)** | Control checklist auto-generated from risk score; evidence attachments; ability to mark conditional approval | Rubber-stamping under pressure; being asked to approve outside their delegated authority | Recommends approve / conditional / reject; escalates above threshold |
| **Engineering / Product Requestor** | Plain-language intake form; clear status visibility; predictable SLA; knowing what they need to provide upfront | Submitting and never hearing back; being blocked on a pilot by a process they can't see into | Owns the use case; responsible for implementing conditions |
| **Authorizing Official (AO)** | One-page review packet per decision; immutable history; clear scope of what was authorized | Signing an authorization that doesn't match what was actually built or that has silently expanded | Issues authorization; can revoke |
| **Internal Audit / IG Liaison** | Read-only audit trail; exportable decision log; ability to sample use cases against policy | Being unable to reconstruct a decision when asked; finding gaps between approved scope and actual use | None operationally; identifies findings |

The "fear" column is load-bearing. Every screen, every notification, and every required field in the workbench should reduce one of these fears. If a feature doesn't, it is overhead.

---

## 3. Requirements

### Functional (FR)

1. **FR-01 Intake form** — capture use case, sponsor, business purpose, data types touched, model and hosting, integration points, intended users, and go-live target.
2. **FR-02 Data classification** — structured questions that produce a classification (Public / Internal / Sensitive / CUI) without requiring the requestor to know the taxonomy.
3. **FR-03 Risk scoring** — deterministic rule engine computes a risk tier (Low / Moderate / High) from intake answers; logic is inspectable.
4. **FR-04 Control recommendations** — risk tier maps to a control checklist drawn from a policy template (NIST AI RMF + agency overlay).
5. **FR-05 Workflow state machine** — enforces lifecycle: Draft → Submitted → Triage → Security Review → Privacy Review → Conditional Approval → Approved / Rejected → Re-review Required.
6. **FR-06 Reviewer assignment** — routes by role and risk tier; supports reassignment with reason.
7. **FR-07 Reviewer comments** — threaded, attributable, timestamped; visible to requestor.
8. **FR-08 Conditions on approval** — approvers attach named conditions that requestor must acknowledge; conditions surface in re-review.
9. **FR-09 Evidence attachments** — upload architecture diagrams, DPIAs, vendor contracts, model cards; each attachment versioned.
10. **FR-10 Decision packet export** — generate a single Markdown/PDF packet per decision: intake, score, controls, conditions, comments, signatures.
11. **FR-11 Re-review scheduling** — every approval carries an expiration; system surfaces upcoming and overdue re-reviews.
12. **FR-12 Portfolio dashboard** — counts and lists by status, risk tier, owner, expiration; CSV export.
13. **FR-13 Role-based access** — six roles with explicit permissions; no role can both submit and approve the same use case.
14. **FR-14 Search and filter** — by sponsor, data type, model, vendor, status, tier.
15. **FR-15 Audit log** — every state transition, comment, attachment, and field change written to an append-only log.

### Non-Functional (NFR)

1. **NFR-01 Auditability** — every user-visible action is reconstructable from the log alone.
2. **NFR-02 Separation of duties** — enforced in code, not policy: requestor cannot approve; same reviewer cannot serve as both privacy and security on one case.
3. **NFR-03 Data minimization** — intake collects only fields used by the rubric or the packet; no free-text fields where a structured choice exists.
4. **NFR-04 Traceability** — each requirement, control, and risk has a stable ID referenced across spec, code, and tests.
5. **NFR-05 Local deployment** — runs as a single `docker compose up` for the demo, no external dependencies.
6. **NFR-06 Accessibility** — WCAG 2.1 AA on all reviewer screens; intake form usable by keyboard.

---

## 4. Sample Use Cases (illustrative, drive requirements concrete)

These three cases are processed end-to-end in the demo. They were chosen to exercise different risk axes:

- **UC-1: Internal policy Q&A copilot** — RAG assistant over HR and security policies, hosted on agency-tenant Azure OpenAI. *Stresses:* data classification (employee PII), CUI handling in prompts, hallucination risk in policy answers.
- **UC-2: Contract clause extraction** — commercial LLM API extracts clauses from procurement contracts. *Stresses:* vendor / hosting boundary (data leaves agency), contract terms sensitivity, training-data exposure.
- **UC-3: Facility predictive maintenance** — ML model predicts HVAC failures from building telemetry. *Stresses:* CIA shift toward integrity/availability, OT-adjacent system, no PII but operationally critical.

If the workbench cannot tell these three cases apart in its risk scoring and control output, the rubric is wrong.

---

## 5. Assumptions

The design rests on these bets. If any flips, the design must be revisited.

- **Human-in-the-loop is mandatory.** No use case auto-approves regardless of risk tier. The workbench is a workflow, not a gate.
- **Reviewers will engage within SLA.** A 5-business-day SLA per review stage is realistic for Low/Moderate; High requires sync convening. If reviewers are unavailable, the workbench escalates rather than expires.
- **Sample / synthetic data only in v1.** No live ingestion of agency systems; no real PII or CUI in the demo environment.
- **Single-tenant.** One agency, one policy template, one set of reviewers per instance.
- **English-only interface.** Translation is out of scope.
- **AI suggestions are advisory.** Any LLM-generated summary, control recommendation, or red-flag callout is labeled, attributable to the model, and overridable by a human reviewer.
- **Intake is completed by the requestor, not by security on their behalf.** The workbench educates the requestor; it does not let security ghost-write submissions.
- **Some form of policy already exists.** The workbench operationalizes existing policy; it does not replace the agency's AI policy authoring process.

---

## 6. Constraints

Hard boundaries the design will not cross.

- **No production sensitive data** in the demo or any non-production deployment.
- **No enforcement coupling.** The workbench records authorizations; it does not call into production systems to allow or block model usage.
- **No enterprise SSO in v1.** Local accounts with role assignment; SSO is a v2 integration.
- **Single-container demo.** Must run on a laptop with `docker compose up` and seed data.
- **Audit log immutability.** Append-only at the application layer; no UI affordance to edit or delete log entries; backed by hash-chained rows.
- **AI outputs labeled and reversible.** Every AI-generated artifact carries a visible "AI-generated, advisory only" marker and can be discarded without affecting the underlying record.
- **No model training on submitted content.** Any LLM features use APIs with zero-retention terms; this constraint is documented in the system's own SSP-style description.
- **No automated scanning of the agency environment.** The workbench accepts what is submitted; it does not crawl for shadow AI in v1.

---

## 7. Major Risks

| ID | Risk | Category | Likelihood | Impact | Mitigation |
|---|---|---|---|---|---|
| R-01 | Workbench becomes a paperwork ritual that requestors route around (shadow AI persists) | Adoption | H | H | Keep intake under 15 minutes for Low-tier cases; publish SLA and hit it; make the legitimate path visibly faster than asking around |
| R-02 | Risk rubric mis-scores a high-risk case as Low (false negative) | Governance | M | H | Rubric is inspectable and versioned; quarterly calibration against actual incidents; reviewer can override tier with logged reason |
| R-03 | Reviewers rubber-stamp under volume pressure | Governance | H | M | Dashboard exposes per-reviewer approval rates and time-to-decision; conditions-attached rate is a leading indicator of engagement |
| R-04 | AI summarization feature leaks submitted content to a third-party model | AI-specific | M | H | Zero-retention API terms enforced in code (provider allowlist); no AI features on CUI-classified cases; feature can be disabled per deployment |
| R-05 | Approved use case silently expands beyond authorized scope | Governance | H | M | Re-review triggered by material change checklist (model, vendor, data type, user population); requestor attestation at re-review |
| R-06 | Audit log is mutable in practice (DB access, log rotation, restore-from-backup) | Technical | M | H | Hash-chained log rows; nightly external attestation of chain head; restore procedure documented and tested |
| R-07 | Separation of duties enforced in UI but bypassable via API | Technical | M | H | SoD checks in the service layer, not the controller; integration tests cover direct API calls; no admin role can override |
| R-08 | Reflexivity — AI features inside the governance tool itself are ungoverned | Meta / AI-specific | H | M | The workbench's own AI features are themselves entered as a use case in the workbench and approved through the same workflow; documented in the demo script |
| R-09 | Policy template drifts out of sync with agency policy of record | Governance | M | M | Template carries a version and effective date; dashboard surfaces "decisions made under superseded policy"; re-review on policy change |
| R-10 | Demo fidelity gap — looks polished, hides that it depends on assumptions a real agency wouldn't accept | Adoption | M | M | Assumptions section (this doc) ships with the demo; "what would change in production" appendix in the README |

R-08 is the one to lead with in interviews. A governance tool that exempts its own AI from governance fails its own thesis.

---

## 8. Out of Scope (v1)

Stated explicitly so the design does not drift:

- Enterprise identity integration (SSO, SCIM)
- Automated discovery of AI usage across the environment
- Direct enforcement in production systems (gateway, proxy, runtime block)
- Multi-tenant / multi-agency
- Vendor risk management beyond what fits in the intake
- Continuous model monitoring (drift, bias drift, accuracy decay)
- Workflow customization per agency in the UI (config is code in v1)
