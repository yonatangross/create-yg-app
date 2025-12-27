"""Tests for LLM factory."""

import pytest

from app.core.config import get_settings
from app.llm.factory import LLMFactory


class TestLLMFactory:
    """Tests for LLMFactory."""

    def test_create_requires_api_key(self, monkeypatch):
        """Should raise error if no API key is set."""
        get_settings.cache_clear()
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("GOOGLE_API_KEY", "")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")

        with pytest.raises(ValueError, match="API key"):
            LLMFactory.create()

    def test_create_openai(self, monkeypatch):
        """Should create OpenAI LLM when API key is set."""
        get_settings.cache_clear()
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")

        llm = LLMFactory.create()
        assert llm is not None

    def test_provider_inference(self, monkeypatch):
        """Should infer provider from model name."""
        get_settings.cache_clear()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("LLM_MODEL", "claude-3-sonnet")

        llm = LLMFactory.create()
        assert llm is not None
