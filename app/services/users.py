from sqlmodel import Session, select

from app.models import User, UserRole


def create_user(
    session: Session, *, email: str, name: str, role: UserRole, password: str
) -> User:
    from app.auth import hash_password  # avoid import cycle at module load

    user = User(
        email=email,
        name=name,
        role=role,
        password_hash=hash_password(password),
        active=True,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()
