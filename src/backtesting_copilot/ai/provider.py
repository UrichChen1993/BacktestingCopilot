"""LLM provider abstraction with an offline rule-based fallback.

Selection: env LLM_PROVIDER (claude|openai|offline). Missing keys fall back to
offline so the whole system runs without any external API (PRD §9.1).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import Settings, get_settings


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return a natural-language completion for ``prompt``."""
        ...


class OfflineProvider:
    """Deterministic, no-network provider. Echoes a structured note so the
    advisor/analyst can still produce rule-based output without an LLM."""

    name = "offline"

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return (
            "[offline] No LLM configured; using rule-based output. "
            "Set LLM_PROVIDER and an API key to enable AI narration."
        )


class ClaudeProvider:
    """Anthropic Claude provider (requires `anthropic` and ANTHROPIC_API_KEY)."""

    name = "claude"

    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import Anthropic  # imported lazily

        self._client = Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system or "You are a quant strategy analyst. Be concise and factual.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class OpenAIProvider:
    """OpenAI provider (requires `openai` and OPENAI_API_KEY)."""

    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI  # imported lazily

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system or "You are a quant strategy analyst."},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Resolve the configured provider, degrading to offline on any gap."""
    settings = settings or get_settings()
    choice = (settings.llm_provider or "offline").lower()
    try:
        if choice == "claude" and settings.anthropic_api_key:
            return ClaudeProvider(settings.anthropic_api_key, settings.claude_model)
        if choice == "openai" and settings.openai_api_key:
            return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    except Exception:  # noqa: BLE001 - never let provider init break the app
        return OfflineProvider()
    return OfflineProvider()
