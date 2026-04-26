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
    state = apply(current=state, action=Action.auto_triage, actor_role=UserRole.security_reviewer)
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


# SR-17: requestor and auditor must not be able to trigger auto_triage
def test_requestor_cannot_auto_triage() -> None:
    with pytest.raises(StateMachineError):
        apply(current=UseCaseStatus.submitted, action=Action.auto_triage, actor_role=UserRole.requestor)


def test_auditor_cannot_auto_triage() -> None:
    with pytest.raises(StateMachineError):
        apply(current=UseCaseStatus.submitted, action=Action.auto_triage, actor_role=UserRole.auditor)
