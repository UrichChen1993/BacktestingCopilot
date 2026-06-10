"""TDD coverage for LLM provider *selection* (PRD §7).

Real API calls (Claude/OpenAI/Gemini/Ollama) are manual/integration tests; here
we only lock the dependency-free decision logic and the offline fallback so the
system always runs without keys.
"""

from __future__ import annotations

from backtesting_copilot.ai.provider import OfflineProvider, _resolve_choice, get_provider
from backtesting_copilot.config import Settings


def test_cloud_providers_require_their_key():
    assert _resolve_choice(Settings(llm_provider="claude", anthropic_api_key="k")) == "claude"
    assert _resolve_choice(Settings(llm_provider="claude", anthropic_api_key="")) == "offline"
    assert _resolve_choice(Settings(llm_provider="openai", openai_api_key="k")) == "openai"
    assert _resolve_choice(Settings(llm_provider="openai", openai_api_key="")) == "offline"
    assert _resolve_choice(Settings(llm_provider="gemini", gemini_api_key="k")) == "gemini"
    assert _resolve_choice(Settings(llm_provider="gemini", gemini_api_key="")) == "offline"


def test_ollama_needs_no_key():
    # local server; selection should not require an API key
    assert _resolve_choice(Settings(llm_provider="ollama")) == "ollama"


def test_unknown_or_offline_resolves_to_offline():
    assert _resolve_choice(Settings(llm_provider="offline")) == "offline"
    assert _resolve_choice(Settings(llm_provider="banana")) == "offline"


def test_get_provider_falls_back_to_offline_without_config():
    assert isinstance(get_provider(Settings(llm_provider="offline")), OfflineProvider)
    # a cloud choice with no key must never raise, just degrade
    assert isinstance(get_provider(Settings(llm_provider="gemini", gemini_api_key="")), OfflineProvider)
