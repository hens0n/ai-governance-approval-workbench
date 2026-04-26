from app.llm import get_llm_client
from app.llm.noop import NoopLLMClient


def test_default_client_is_noop_when_disabled(monkeypatch) -> None:
    from app import config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "ai_features_enabled", False)
    client = get_llm_client(classification="internal")
    assert isinstance(client, NoopLLMClient)


def test_cui_classification_forces_noop_even_when_enabled(monkeypatch) -> None:
    from app import config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "ai_features_enabled", True)
    client = get_llm_client(classification="cui")
    assert isinstance(client, NoopLLMClient)


def test_noop_returns_advisory_placeholder() -> None:
    client = NoopLLMClient()
    art = client.summarize_intake(use_case_title="t", intake={"k": "v"})
    assert art.advisory is True
    assert "disabled" in art.content.lower()
