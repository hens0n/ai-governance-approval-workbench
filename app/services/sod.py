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
