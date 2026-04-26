from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import current_user, writer_user
from app.db import get_session
from app.models import ReviewDecision, ReviewRole, StateTransition, UseCase, User, UserRole
from app.services.expiring import expiring_soon
from app.services.lifecycle import LifecycleService
from app.workflow import allowed_actions

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# Length caps on free-text fields to prevent DB-bloat DoS via reviewer accounts.
_MAX_NARRATIVE = 4000
_MAX_REASON = 4000
_MAX_CONDITION_FIELD = 1000
_MAX_CONDITIONS_PER_REVIEW = 50

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"user": None})


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> HTMLResponse:
    use_cases = session.exec(select(UseCase).order_by(UseCase.id.desc())).all()
    by_status: dict[str, int] = {}
    for uc in use_cases:
        by_status[uc.status.value] = by_status.get(uc.status.value, 0) + 1
    expiring_rows = expiring_soon(session)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "use_cases": use_cases,
            "by_status": by_status,
            "expiring_rows": expiring_rows,
        },
    )


@router.get("/use-cases/new", response_class=HTMLResponse)
def new_page(
    request: Request, user: Annotated[User, Depends(current_user)]
) -> HTMLResponse:
    return templates.TemplateResponse(request, "use_case_new.html", {"user": user})


@router.post("/ui/use-cases", response_class=HTMLResponse)
def create_use_case(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
    title: Annotated[str, Form()],
    business_purpose: Annotated[str, Form()],
    model_name: Annotated[str, Form()],
    hosting: Annotated[str, Form()],
) -> RedirectResponse:
    svc = LifecycleService(session)
    uc = svc.create_draft(
        sponsor_id=user.id,
        title=title,
        business_purpose=business_purpose,
        model_name=model_name,
        hosting=hosting,
    )
    session.commit()
    return RedirectResponse(url=f"/use-cases/{uc.id}", status_code=303)


@router.get("/use-cases/{use_case_id}", response_class=HTMLResponse)
def detail(
    use_case_id: int,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> HTMLResponse:
    uc = session.get(UseCase, use_case_id)
    if uc is None:
        raise HTTPException(404)
    transitions = session.exec(
        select(StateTransition)
        .where(StateTransition.use_case_id == use_case_id)
        .order_by(StateTransition.created_at.asc())
    ).all()
    allowed = [a.value for a in allowed_actions(uc.status, user.role)]
    security_candidates: list[User] = []
    privacy_candidates: list[User] = []
    if "assign_reviewers" in allowed:
        security_candidates = session.exec(
            select(User)
            .where(User.role == UserRole.security_reviewer, User.id != uc.sponsor_id, User.id != user.id)
            .order_by(User.email)
        ).all()
        privacy_candidates = session.exec(
            select(User)
            .where(User.role == UserRole.privacy_reviewer, User.id != uc.sponsor_id)
            .order_by(User.email)
        ).all()
    return templates.TemplateResponse(
        request,
        "use_case_detail.html",
        {
            "user": user,
            "uc": uc,
            "transitions": transitions,
            "allowed": allowed,
            "security_candidates": security_candidates,
            "privacy_candidates": privacy_candidates,
        },
    )


@router.post("/ui/use-cases/{use_case_id}/assign_reviewers", response_class=HTMLResponse)
def ui_assign_reviewers(
    use_case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
    security_id: Annotated[int, Form()],
    privacy_id: Annotated[int, Form()],
) -> RedirectResponse:
    svc = LifecycleService(session)
    try:
        svc.assign_reviewers(
            use_case_id=use_case_id,
            actor_id=user.id,
            security_id=security_id,
            privacy_id=privacy_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RedirectResponse(url=f"/use-cases/{use_case_id}", status_code=303)


@router.post("/ui/use-cases/{use_case_id}/request_revision", response_class=HTMLResponse)
def ui_request_revision(
    use_case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
    reason: Annotated[str, Form()],
) -> RedirectResponse:
    if len(reason) > _MAX_REASON:
        raise HTTPException(400, f"reason exceeds {_MAX_REASON}-character limit")
    svc = LifecycleService(session)
    try:
        svc.request_revision(use_case_id=use_case_id, actor_id=user.id, reason=reason)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RedirectResponse(url=f"/use-cases/{use_case_id}", status_code=303)


@router.post("/ui/use-cases/{use_case_id}/submit_review", response_class=HTMLResponse)
def ui_submit_review(
    use_case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
    decision: Annotated[str, Form()],
    narrative: Annotated[str, Form()] = "",
    condition_names: Annotated[list[str], Form()] = [],
    condition_descriptions: Annotated[list[str], Form()] = [],
) -> RedirectResponse:
    role_map = {
        UserRole.security_reviewer: ReviewRole.security,
        UserRole.privacy_reviewer: ReviewRole.privacy,
    }
    if user.role not in role_map:
        raise HTTPException(403, "only security or privacy reviewers may submit reviews")
    if len(narrative) > _MAX_NARRATIVE:
        raise HTTPException(400, f"narrative exceeds {_MAX_NARRATIVE}-character limit")
    if len(condition_names) > _MAX_CONDITIONS_PER_REVIEW or len(condition_descriptions) > _MAX_CONDITIONS_PER_REVIEW:
        raise HTTPException(400, f"too many conditions (limit {_MAX_CONDITIONS_PER_REVIEW} per submission)")
    for value in (*condition_names, *condition_descriptions):
        if len(value) > _MAX_CONDITION_FIELD:
            raise HTTPException(400, f"condition field exceeds {_MAX_CONDITION_FIELD}-character limit")
    try:
        decision_enum = ReviewDecision(decision)
    except ValueError:
        raise HTTPException(400, f"invalid decision: {decision}")

    conditions = [
        {"name": n.strip(), "description": d.strip()}
        for n, d in zip(condition_names, condition_descriptions)
        if n.strip() and d.strip()
    ]
    if decision_enum == ReviewDecision.conditional and not conditions:
        raise HTTPException(400, "at least one condition is required for a conditional review")

    svc = LifecycleService(session)
    try:
        svc.submit_review(
            use_case_id=use_case_id,
            reviewer_id=user.id,
            role=role_map[user.role],
            decision=decision_enum,
            narrative=narrative.strip(),
            conditions=conditions,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RedirectResponse(url=f"/use-cases/{use_case_id}", status_code=303)


@router.post("/ui/use-cases/{use_case_id}/{action}", response_class=HTMLResponse)
def ui_transition(
    use_case_id: int,
    action: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
) -> RedirectResponse:
    svc = LifecycleService(session)
    try:
        if action == "submit":
            svc.submit(use_case_id=use_case_id, actor_id=user.id)
        elif action == "auto_triage":
            svc.triage(use_case_id=use_case_id, actor_id=user.id)
        else:
            raise HTTPException(400, f"unsupported UI action: {action}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RedirectResponse(url=f"/use-cases/{use_case_id}", status_code=303)
