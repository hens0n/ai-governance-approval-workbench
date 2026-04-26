from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from app.models import AuditLogEntry

GENESIS_HASH = "0" * 64


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _compute_hash(prev_hash: str, entry_payload: dict) -> str:
    material = prev_hash.encode("utf-8") + b"|" + _canonical_json(entry_payload)
    return hashlib.sha256(material).hexdigest()


class AuditLogWriter:
    """Appends hash-chained entries. Callers own the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _latest_hash(self) -> str:
        stmt = select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(1)
        latest = self._session.exec(stmt).first()
        return latest.hash if latest else GENESIS_HASH

    def append(
        self,
        *,
        actor_id: Optional[int],
        action: str,
        entity_type: str,
        entity_id: int,
        payload: dict,
    ) -> AuditLogEntry:
        prev_hash = self._latest_hash()
        created_at = datetime.now(timezone.utc)
        hash_input = {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "created_at": created_at.isoformat(),
        }
        entry = AuditLogEntry(
            prev_hash=prev_hash,
            hash=_compute_hash(prev_hash, hash_input),
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            created_at=created_at,
        )
        self._session.add(entry)
        self._session.flush()
        return entry


def verify_chain(session: Session) -> tuple[bool, Optional[int]]:
    """Walk the log in order; return (ok, first_bad_id)."""
    stmt = select(AuditLogEntry).order_by(AuditLogEntry.id.asc())
    entries = session.exec(stmt).all()
    prev_hash = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != prev_hash:
            return False, entry.id
        hash_input = {
            "actor_id": entry.actor_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "payload": entry.payload,
            "created_at": entry.created_at.isoformat(),
        }
        expected = _compute_hash(entry.prev_hash, hash_input)
        if expected != entry.hash:
            return False, entry.id
        prev_hash = entry.hash
    return True, None
