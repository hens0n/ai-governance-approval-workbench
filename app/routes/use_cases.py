from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth import current_user, writer_user
from app.db import get_session
from app.models import UseCase, User, UseCaseStatus
from app.services.lifecycle import LifecycleService

router = APIRouter(prefix="/api/use-cases", tags=["use-cases"])


class CreateUseCaseBody(BaseModel):
    title: str
    business_purpose: str
    model_name: str
    hosting: str


class TransitionBody(BaseModel):
    action: str
    payload: dict | None = None


class IntakeBody(BaseModel):
    answers: dict


@router.post("", status_code=201)
def create(
    body: CreateUseCaseBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
) -> dict:
    svc = LifecycleService(session)
    uc = svc.create_draft(
        sponsor_id=user.id,
        title=body.title,
        business_purpose=body.business_purpose,
        model_name=body.model_name,
        hosting=body.hosting,
    )
    session.commit()
    return {"id": uc.id, "status": uc.status.value}


@router.patch("/{use_case_id}/intake")
def patch_intake(
    use_case_id: int,
    body: IntakeBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
) -> dict:
    uc = session.get(UseCase, use_case_id)
    if uc is None:
        raise HTTPException(status_code=404, detail="use case not found")
    if uc.sponsor_id != user.id:
        raise HTTPException(status_code=403, detail="only the sponsor may edit intake answers")
    _EDITABLE_STATUSES = {UseCaseStatus.draft, UseCaseStatus.revision_requested, UseCaseStatus.re_review_required}
    if uc.status not in _EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="use case status does not permit intake edits")
    svc = LifecycleService(session)
    for k, v in body.answers.items():
        svc.upsert_intake_answer(use_case_id=use_case_id, question_key=k, answer_value=v, actor_id=user.id)
    session.commit()
    return {"ok": True}


@router.post("/{use_case_id}/transitions")
def transition(
    use_case_id: int,
    body: TransitionBody,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
) -> dict:
    svc = LifecycleService(session)
    action = body.action
    payload = body.payload or {}
    try:
        if action == "submit":
            svc.submit(use_case_id=use_case_id, actor_id=user.id)
        elif action == "triage":
            svc.triage(use_case_id=use_case_id, actor_id=user.id)
        elif action == "assign_reviewers":
            svc.assign_reviewers(
                use_case_id=use_case_id,
                actor_id=user.id,
                security_id=payload["security_id"],
                privacy_id=payload["privacy_id"],
            )
        elif action == "ao_decide":
            svc.ao_decide(
                use_case_id=use_case_id,
                actor_id=user.id,
                decision=payload["decision"],
                narrative=payload.get("narrative"),
            )
        elif action == "material_change":
            svc.trigger_material_change(
                use_case_id=use_case_id, actor_id=user.id, reason=payload.get("reason", "")
            )
        else:
            raise HTTPException(400, f"unknown action: {action}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    session.commit()
    return {"ok": True}
