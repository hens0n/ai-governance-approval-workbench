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


_SYSTEM_ROLES = frozenset({UserRole.security_reviewer, UserRole.privacy_reviewer, UserRole.ao, UserRole.ciso})
# auditor and requestor are excluded — no system-driven actions
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
