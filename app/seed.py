from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.models import User, UserRole
from app.services.lifecycle import LifecycleService
from app.services.users import create_user

_SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


def seed_if_empty() -> None:
    from app import db as db_mod
    with Session(db_mod.engine) as session:
        if session.exec(select(User)).first() is not None:
            return
        users_data = json.loads((_SEED_DIR / "users.json").read_text())
        email_to_id: dict[str, int] = {}
        for u in users_data:
            created = create_user(
                session,
                email=u["email"], name=u["name"],
                role=UserRole(u["role"]), password=u["password"],
            )
            email_to_id[u["email"]] = created.id
        session.commit()

        cases = json.loads((_SEED_DIR / "use_cases.json").read_text())
        svc = LifecycleService(session)
        for case in cases:
            sponsor_id = email_to_id[case["sponsor_email"]]
            uc = svc.create_draft(
                sponsor_id=sponsor_id,
                title=case["title"],
                business_purpose=case["business_purpose"],
                model_name=case["model_name"],
                hosting=case["hosting"],
            )
            for k, v in case["intake"].items():
                svc.upsert_intake_answer(use_case_id=uc.id, question_key=k, answer_value=v, actor_id=sponsor_id)
            svc.submit(use_case_id=uc.id, actor_id=sponsor_id)
        session.commit()
