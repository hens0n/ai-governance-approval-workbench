from __future__ import annotations

from hashlib import sha256 as _sha256
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.models import Attachment, AttachmentKind
from app.services.audit import AuditLogWriter


def save_attachment(
    session: Session,
    *,
    use_case_id: int,
    uploaded_by: int,
    kind: AttachmentKind,
    filename: str,
    content: bytes,
) -> Attachment:
    digest = _sha256(content).hexdigest()
    target_dir = Path(settings.attachments_dir) / digest[:2]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / digest
    if not target.exists():
        target.write_bytes(content)

    row = Attachment(
        use_case_id=use_case_id,
        kind=kind,
        filename=filename,
        sha256=digest,
        bytes=len(content),
        uploaded_by=uploaded_by,
    )
    session.add(row)
    session.flush()
    AuditLogWriter(session).append(
        actor_id=uploaded_by,
        action="upload_attachment",
        entity_type="attachment",
        entity_id=row.id,
        payload={
            "use_case_id": use_case_id,
            "filename": filename,
            "sha256": digest,
            "kind": kind.value,
            "bytes": len(content),
        },
    )
    return row


def read_attachment_bytes(session: Session, attachment_id: int) -> tuple[Attachment, bytes]:
    row = session.get(Attachment, attachment_id)
    if row is None:
        raise ValueError(f"attachment {attachment_id} not found")
    path = Path(settings.attachments_dir) / row.sha256[:2] / row.sha256
    return row, path.read_bytes()
