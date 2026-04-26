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
