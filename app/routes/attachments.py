from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import Session

from app.auth import current_user, writer_user
from app.db import get_session
from app.models import AttachmentKind, UseCase, User, UserRole
from app.services.attachments import read_attachment_bytes, save_attachment

router = APIRouter(tags=["attachments"])

MAX_BYTES = 50 * 1024 * 1024  # 50 MB


def _safe_content_disposition(filename: str) -> str:
    ascii_fallback = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in filename)
    if not ascii_fallback.strip("_"):
        ascii_fallback = "attachment"
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(filename)}'


def _can_access_use_case(user: User, use_case: UseCase) -> bool:
    if user.role != UserRole.requestor:
        return True  # reviewers, AO, CISO, auditor (download-only) can access any case
    return use_case.sponsor_id == user.id


@router.post("/api/use-cases/{use_case_id}/attachments", status_code=201)
def upload(
    use_case_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(writer_user)],
    kind: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    uc = session.get(UseCase, use_case_id)
    if uc is None:
        raise HTTPException(status_code=404, detail="use case not found")
    if not _can_access_use_case(user, uc):
        raise HTTPException(status_code=403, detail="not authorized to upload to this use case")
    try:
        kind_enum = AttachmentKind(kind)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 50 MB limit")
    row = save_attachment(
        session,
        use_case_id=use_case_id,
        uploaded_by=user.id,
        kind=kind_enum,
        filename=file.filename or "unnamed",
        content=content,
    )
    session.commit()
    return {"id": row.id, "sha256": row.sha256, "bytes": row.bytes}


@router.get("/api/attachments/{attachment_id}")
def download(
    attachment_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    try:
        row, content = read_attachment_bytes(session, attachment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="attachment not found")
    uc = session.get(UseCase, row.use_case_id)
    if uc is None or not _can_access_use_case(user, uc):
        raise HTTPException(status_code=403, detail="not authorized to download this attachment")
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _safe_content_disposition(row.filename)},
    )
