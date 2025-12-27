"""Tests for LLM factory."""

import pytest

from app.llm.factory import LLMFactory


class TestLLMFactory:
    """Tests for LLMFactory.

    Note: These tests patch `settings` directly in the factory module because
    the settings object is imported at module load time. Using monkeypatch.setenv()
    alone doesn't work since the settings singleton already has its values bound.
    """

    def test_create_requires_api_key(self, monkeypatch):
        """Should raise error if no API key is set."""
        # Patch settings directly in factory module (not env vars)
        # This is necessary because factory.py imports settings at module level
        monkeypatch.setattr("app.llm.factory.settings.OPENAI_API_KEY", None)
        monkeypatch.setattr("app.llm.factory.settings.ANTHROPIC_API_KEY", None)
        monkeypatch.setattr("app.llm.factory.settings.GOOGLE_API_KEY", None)

        with pytest.raises(ValueError, match="API.?KEY.*required"):
            LLMFactory.create()

    def test_create_openai(self, monkeypatch):
        """Should create OpenAI LLM when API key is set."""
        # Patch settings to ensure OpenAI key is available
        monkeypatch.setattr("app.llm.factory.settings.OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr("app.llm.factory.settings.ANTHROPIC_API_KEY", None)
        monkeypatch.setattr("app.llm.factory.settings.GOOGLE_API_KEY", None)
        monkeypatch.setattr("app.llm.factory.settings.LLM_MODEL", "gpt-4o-mini")

        llm = LLMFactory.create()
        assert llm is not None

    def test_provider_inference(self, monkeypatch):
        """Should infer provider from model name."""
        # Patch settings for Anthropic
        monkeypatch.setattr("app.llm.factory.settings.OPENAI_API_KEY", None)
        monkeypatch.setattr("app.llm.factory.settings.ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr("app.llm.factory.settings.GOOGLE_API_KEY", None)
        monkeypatch.setattr("app.llm.factory.settings.LLM_MODEL", "claude-3-sonnet")

        llm = LLMFactory.create()
        assert llm is not None
