import pytest

from app.config import Settings


def test_prod_with_default_secret_raises() -> None:
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings(environment="prod", session_secret="dev-only-change-me")


def test_dev_with_default_secret_succeeds() -> None:
    s = Settings(environment="dev", session_secret="dev-only-change-me")
    assert s.environment == "dev"
    assert s.session_secret == "dev-only-change-me"


def test_prod_with_custom_secret_succeeds() -> None:
    s = Settings(environment="prod", session_secret="a-very-secure-random-value-xyz")
    assert s.environment == "prod"
    assert s.session_secret == "a-very-secure-random-value-xyz"
