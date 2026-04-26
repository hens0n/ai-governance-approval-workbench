from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import (
    IntakeAnswer, StateTransition, UseCase, UseCaseStatus, User,
)
from app.services.audit import AuditLogWriter
from app.services.scoring import ScoreResult, score_use_case
from app.services.sod import SoDViolation
from app.workflow import Action, apply


class LifecycleService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditLogWriter(session)

    def create_draft(
        self,
        *,
        sponsor_id: int,
        title: str,
        business_purpose: str,
        model_name: str,
        hosting: str,
    ) -> UseCase:
        uc = UseCase(
            sponsor_id=sponsor_id,
            title=title,
            business_purpose=business_purpose,
            model_name=model_name,
            hosting=hosting,
            status=UseCaseStatus.draft,
            policy_template_version="v1",
            rubric_version="v1",
        )
        self._session.add(uc)
        self._session.flush()
        self._audit.append(
            actor_id=sponsor_id,
            action="create_draft",
            entity_type="use_case",
            entity_id=uc.id,
            payload={"title": title},
        )
        return uc

    def upsert_intake_answer(
        self, *, use_case_id: int, question_key: str, answer_value: Any, actor_id: int
    ) -> IntakeAnswer:
        stmt = (
            select(IntakeAnswer)
            .where(
                IntakeAnswer.use_case_id == use_case_id,
                IntakeAnswer.question_key == question_key,
            )
            .order_by(IntakeAnswer.version.desc())
        )
        latest = self._session.exec(stmt).first()
        version = (latest.version + 1) if latest else 1
        row = IntakeAnswer(
            use_case_id=use_case_id,
            question_key=question_key,
            answer_value={"value": answer_value},
            version=version,
        )
        self._session.add(row)
        self._session.flush()
        self._audit.append(
            actor_id=actor_id,
            action="upsert_intake_answer",
            entity_type="use_case",
            entity_id=use_case_id,
            payload={"question_key": question_key, "version": version},
        )
        return row

    def _collect_current_intake(self, use_case_id: int) -> dict[str, Any]:
        stmt = (
            select(IntakeAnswer)
            .where(IntakeAnswer.use_case_id == use_case_id)
            .order_by(IntakeAnswer.question_key, IntakeAnswer.version.desc())
        )
        rows = self._session.exec(stmt).all()
        current: dict[str, Any] = {}
        for row in rows:
            if row.question_key in current:
                continue
            current[row.question_key] = row.answer_value.get("value")
        return current

    def _record_transition(
        self,
        *,
        use_case_id: int,
        from_state: UseCaseStatus,
        to_state: UseCaseStatus,
        actor_id: int,
        action: str,
        reason: str | None = None,
        extra_payload: dict | None = None,
    ) -> None:
        self._session.add(
            StateTransition(
                use_case_id=use_case_id,
                from_state=from_state,
                to_state=to_state,
                actor_id=actor_id,
                reason=reason,
            )
        )
        payload = {"from": from_state.value, "to": to_state.value}
        if reason:
            payload["reason"] = reason
        if extra_payload:
            payload.update(extra_payload)
        self._audit.append(
            actor_id=actor_id,
            action=action,
            entity_type="use_case",
            entity_id=use_case_id,
            payload=payload,
        )

    def submit(self, *, use_case_id: int, actor_id: int) -> UseCase:
        uc = self._session.get(UseCase, use_case_id)
        if uc is None:
            raise ValueError(f"use case {use_case_id} not found")
        actor = self._session.get(User, actor_id)
        if actor is None:
            raise ValueError(f"actor {actor_id} not found")
        if actor_id != uc.sponsor_id:
            raise SoDViolation(
                f"only the sponsor may submit use case {use_case_id} (actor={actor_id})"
            )

        answers = self._collect_current_intake(use_case_id)
        score: ScoreResult = score_use_case(answers)
        new_state = apply(current=uc.status, action=Action.submit, actor_role=actor.role)
        from_state = uc.status
        uc.status = new_state
        uc.risk_tier = score.tier
        uc.classification = score.classification
        uc.rubric_version = score.rubric_version
        uc.updated_at = datetime.now(timezone.utc)
        self._session.add(uc)
        self._record_transition(
            use_case_id=uc.id,
            from_state=from_state,
            to_state=new_state,
            actor_id=actor_id,
            action="submit",
            extra_payload={
                "risk_tier": score.tier.value,
                "classification": score.classification.value,
                "breakdown": score.breakdown,
            },
        )
        return uc

    # --- triage / review / AO ----------------------------------------------

    def triage(self, *, use_case_id: int, actor_id: int) -> UseCase:
        from app.services.sod import ensure_not_sponsor

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=actor_id)
        new_state = apply(
            current=uc.status, action=Action.auto_triage, actor_role=actor.role
        )
        self._transition(uc, new_state, actor_id=actor_id, action_name="auto_triage")
        return uc

    def request_revision(
        self, *, use_case_id: int, actor_id: int, reason: str
    ) -> UseCase:
        from app.services.sod import ensure_not_sponsor

        if not reason or not reason.strip():
            raise ValueError("reason is required when requesting revision")

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=actor_id)
        new_state = apply(
            current=uc.status, action=Action.request_revision, actor_role=actor.role
        )
        self._transition(
            uc,
            new_state,
            actor_id=actor_id,
            action_name="request_revision",
            reason=reason.strip(),
        )
        return uc

    def assign_reviewers(
        self, *, use_case_id: int, actor_id: int, security_id: int, privacy_id: int
    ) -> UseCase:
        from app.models import ReviewRole
        from app.services.sod import (
            ensure_not_sponsor,
            ensure_triager_not_reviewer,
            ensure_unique_cross_cycle_roles,
        )

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)

        for candidate, role in (
            (security_id, ReviewRole.security),
            (privacy_id, ReviewRole.privacy),
        ):
            ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=candidate)
            ensure_unique_cross_cycle_roles(
                self._session, use_case_id=use_case_id, actor_id=candidate, target_role=role
            )
            ensure_triager_not_reviewer(
                self._session, use_case_id=use_case_id, actor_id=candidate, target_role=role
            )

        new_state = apply(
            current=uc.status, action=Action.assign_reviewers, actor_role=actor.role
        )
        self._transition(
            uc,
            new_state,
            actor_id=actor_id,
            action_name="assign_reviewers",
            extra_payload={"security_id": security_id, "privacy_id": privacy_id},
        )
        return uc

    def submit_review(
        self,
        *,
        use_case_id: int,
        reviewer_id: int,
        role,
        decision,
        narrative: str,
        conditions: list[dict],
    ):
        from app.models import Condition, ConditionStatus, Review, ReviewRole as _RR
        from app.services.sod import (
            ensure_not_sponsor,
            ensure_triager_not_reviewer,
            ensure_unique_cross_cycle_roles,
        )

        uc = self._require_use_case(use_case_id)
        self._require_user(reviewer_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=reviewer_id)
        ensure_unique_cross_cycle_roles(
            self._session, use_case_id=use_case_id, actor_id=reviewer_id, target_role=role
        )
        ensure_triager_not_reviewer(
            self._session, use_case_id=use_case_id, actor_id=reviewer_id, target_role=role
        )

        review = Review(
            use_case_id=use_case_id,
            reviewer_id=reviewer_id,
            role=role,
            decision=decision,
            narrative=narrative,
        )
        self._session.add(review)
        self._session.flush()
        for c in conditions:
            self._session.add(
                Condition(
                    use_case_id=use_case_id,
                    name=c["name"],
                    description=c["description"],
                    status=ConditionStatus.proposed,
                    source_review_id=review.id,
                )
            )

        self._audit.append(
            actor_id=reviewer_id,
            action="submit_review",
            entity_type="use_case",
            entity_id=use_case_id,
            payload={
                "review_id": review.id,
                "role": role.value,
                "decision": decision.value,
                "conditions": [c["name"] for c in conditions],
            },
        )

        roles_seen = {
            r.role
            for r in self._session.exec(
                select(Review).where(Review.use_case_id == use_case_id)
            ).all()
        }
        if {_RR.security, _RR.privacy}.issubset(roles_seen):
            self._transition(
                uc,
                UseCaseStatus.ao_decision,
                actor_id=reviewer_id,
                action_name="auto_advance",
                via_state_machine=False,
            )
        return review

    def ao_decide(
        self,
        *,
        use_case_id: int,
        actor_id: int,
        decision: str,
        narrative: str | None = None,
        accepted_condition_ids="all",
        re_review_days_by_tier: dict[str, int] | None = None,
    ) -> UseCase:
        from datetime import timedelta

        from app.models import Condition, ConditionStatus, ReReview, ReReviewTrigger
        from app.services.sod import ensure_ao_clean, ensure_not_sponsor

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)
        ensure_not_sponsor(self._session, use_case_id=use_case_id, actor_id=actor_id)
        ensure_ao_clean(self._session, use_case_id=use_case_id, actor_id=actor_id)

        action_map = {
            "approve": (Action.approve, UseCaseStatus.approved),
            "approve_with_conditions": (
                Action.approve_with_conditions,
                UseCaseStatus.conditionally_approved,
            ),
            "reject": (Action.reject, UseCaseStatus.rejected),
            "send_back": (Action.send_back, UseCaseStatus.revision_requested),
        }
        if decision not in action_map:
            raise ValueError(f"unknown AO decision: {decision}")
        action_enum, target_state = action_map[decision]
        apply(current=uc.status, action=action_enum, actor_role=actor.role)

        if decision == "approve_with_conditions":
            stmt = select(Condition).where(
                Condition.use_case_id == use_case_id,
                Condition.status == ConditionStatus.proposed,
            )
            conds = self._session.exec(stmt).all()
            if accepted_condition_ids == "all":
                for c in conds:
                    c.status = ConditionStatus.accepted
                    self._session.add(c)
            else:
                id_set = set(accepted_condition_ids)
                for c in conds:
                    if c.id in id_set:
                        c.status = ConditionStatus.accepted
                        self._session.add(c)

        self._transition(
            uc, target_state, actor_id=actor_id, action_name=decision, reason=narrative,
            via_state_machine=False,
        )

        if target_state in (UseCaseStatus.approved, UseCaseStatus.conditionally_approved):
            defaults = re_review_days_by_tier or {"low": 365, "moderate": 180, "high": 90}
            days = defaults[uc.risk_tier.value] if uc.risk_tier else 365
            self._session.add(
                ReReview(
                    use_case_id=use_case_id,
                    due_date=datetime.now(timezone.utc) + timedelta(days=days),
                    trigger=ReReviewTrigger.scheduled,
                )
            )
        return uc

    # --- helpers ----------------------------------------------------------

    def _require_use_case(self, use_case_id: int) -> UseCase:
        uc = self._session.get(UseCase, use_case_id)
        if uc is None:
            raise ValueError(f"use case {use_case_id} not found")
        return uc

    def _require_user(self, user_id: int) -> User:
        u = self._session.get(User, user_id)
        if u is None:
            raise ValueError(f"user {user_id} not found")
        return u

    def _transition(
        self,
        uc: UseCase,
        to_state: UseCaseStatus,
        *,
        actor_id: int,
        action_name: str,
        reason: str | None = None,
        extra_payload: dict | None = None,
        via_state_machine: bool = True,
    ) -> None:
        from_state = uc.status
        uc.status = to_state
        uc.updated_at = datetime.now(timezone.utc)
        self._session.add(uc)
        self._record_transition(
            use_case_id=uc.id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            action=action_name,
            reason=reason,
            extra_payload=extra_payload,
        )

    def check_expirations(self, *, actor_id: int) -> list[int]:
        from datetime import datetime, timezone

        from app.models import ReReview

        now = datetime.now(timezone.utc)
        stmt = (
            select(UseCase, ReReview)
            .join(ReReview, ReReview.use_case_id == UseCase.id)
            .where(
                UseCase.status.in_(
                    [UseCaseStatus.approved, UseCaseStatus.conditionally_approved]
                ),
                ReReview.due_date <= now,
                ReReview.completed_at.is_(None),
            )
        )
        moved: list[int] = []
        for uc, _rr in self._session.exec(stmt).all():
            self._transition(
                uc,
                UseCaseStatus.re_review_required,
                actor_id=actor_id,
                action_name="expire",
                via_state_machine=False,
            )
            moved.append(uc.id)
        return moved

    def trigger_material_change(self, *, use_case_id: int, actor_id: int, reason: str) -> UseCase:
        from app.models import ReReview, ReReviewTrigger, UserRole

        uc = self._require_use_case(use_case_id)
        actor = self._require_user(actor_id)
        if actor.role not in (UserRole.ao, UserRole.ciso) and uc.sponsor_id != actor_id:
            raise SoDViolation(
                "only the sponsor, AO, or CISO may trigger a material change"
            )
        self._session.add(
            ReReview(
                use_case_id=use_case_id,
                due_date=datetime.now(timezone.utc),
                trigger=ReReviewTrigger.material_change,
            )
        )
        self._transition(
            uc,
            UseCaseStatus.re_review_required,
            actor_id=actor_id,
            action_name="expire",
            reason=reason,
            via_state_machine=False,
        )
        return uc
