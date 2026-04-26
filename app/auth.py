from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.models import User, UserRole
from app.services.users import get_user_by_email

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")
_serializer = URLSafeSerializer(settings.session_secret, salt="session")

login_router = APIRouter()


def hash_password(plaintext: str) -> str:
    return _pwd.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    return _pwd.verify(plaintext, hashed)


def _make_cookie(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def _read_cookie(token: str) -> int | None:
    try:
        data = _serializer.loads(token)
    except (BadSignature, ValueError):
        return None
    return data.get("uid") if isinstance(data, dict) else None


def current_user(
    session: Annotated[Session, Depends(get_session)],
    session_token: Annotated[str | None, Cookie(alias="session")] = None,
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not signed in")
    uid = _read_cookie(session_token)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    user = session.get(User, uid)
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="inactive user")
    return user


WRITE_CAPABLE_ROLES = {UserRole.requestor, UserRole.security_reviewer, UserRole.privacy_reviewer, UserRole.ao, UserRole.ciso}
# auditor is intentionally read-only


def require_role(*roles: UserRole):
    def _guard(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="role not permitted")
        return user

    return Depends(_guard)


def writer_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role == UserRole.auditor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="auditor is read-only")
    return user


@login_router.post("/login")
def login(
    session: Annotated[Session, Depends(get_session)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = get_user_by_email(session, email)
    if not user or not user.active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        "session", _make_cookie(user.id), httponly=True, samesite="lax", secure=False
    )
    return response


@login_router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
