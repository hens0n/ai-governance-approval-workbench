from sqlalchemy import create_engine as _ce
from sqlmodel import Session, SQLModel, select


def test_seed_creates_users_and_cases(monkeypatch, tmp_path) -> None:
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    new_engine = _ce(cfg_mod.settings.database_url)
    from app import db as db_mod
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)

    from app.seed import seed_if_empty
    from app.models import UseCase, User

    seed_if_empty()

    with Session(new_engine) as session:
        users = session.exec(select(User)).all()
        assert len(users) == 7
        cases = session.exec(select(UseCase)).all()
        assert len(cases) == 3
        titles = {c.title for c in cases}
        assert "Internal policy Q&A copilot" in titles
        assert "Contract clause extraction" in titles
        assert "Facility predictive maintenance" in titles


def test_seed_is_idempotent(monkeypatch, tmp_path) -> None:
    db = tmp_path / "t.db"
    from app import config as cfg_mod
    monkeypatch.setattr(cfg_mod.settings, "database_url", f"sqlite:///{db}")
    new_engine = _ce(cfg_mod.settings.database_url)
    from app import db as db_mod
    monkeypatch.setattr(db_mod, "engine", new_engine)
    SQLModel.metadata.create_all(new_engine)

    from app.seed import seed_if_empty
    from app.models import UseCase, User

    seed_if_empty()
    seed_if_empty()

    with Session(new_engine) as session:
        assert len(session.exec(select(User)).all()) == 7
        assert len(session.exec(select(UseCase)).all()) == 3
