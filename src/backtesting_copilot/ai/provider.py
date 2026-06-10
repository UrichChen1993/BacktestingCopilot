"""LLM provider abstraction with an offline rule-based fallback.

Selection: env LLM_PROVIDER (claude|openai|gemini|ollama|offline). Missing keys
fall back to offline so the whole system runs without any external API
(PRD §9.1). Ollama is local (OpenAI-compatible) and needs no key.
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


class GeminiProvider:
    """Google Gemini provider (requires `google-genai` and GEMINI_API_KEY)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai  # imported lazily

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        content = f"{system}\n\n{prompt}" if system else prompt
        resp = self._client.models.generate_content(model=self._model, contents=content)
        return resp.text or ""


class OllamaProvider:
    """Local Ollama via its OpenAI-compatible endpoint (requires `openai` and a
    running `ollama serve`). No API key needed — the key field is ignored."""

    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        from openai import OpenAI  # imported lazily

        self._client = OpenAI(base_url=base_url, api_key="ollama")
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


def _resolve_choice(settings: Settings) -> str:
    """Pick the provider name from settings, requiring a key for cloud providers.

    Dependency-free (no SDK imports) so it is fully unit-testable. Ollama is
    local and needs no key; anything unrecognised or unconfigured -> offline.
    """
    choice = (settings.llm_provider or "offline").lower()
    if choice == "claude" and settings.anthropic_api_key:
        return "claude"
    if choice == "openai" and settings.openai_api_key:
        return "openai"
    if choice == "gemini" and settings.gemini_api_key:
        return "gemini"
    if choice == "ollama":
        return "ollama"
    return "offline"


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Resolve the configured provider, degrading to offline on any gap."""
    settings = settings or get_settings()
    choice = _resolve_choice(settings)
    try:
        if choice == "claude":
            return ClaudeProvider(settings.anthropic_api_key, settings.claude_model)
        if choice == "openai":
            return OpenAIProvider(settings.openai_api_key, settings.openai_model)
        if choice == "gemini":
            return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
        if choice == "ollama":
            return OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    except Exception:  # noqa: BLE001 - never let provider init break the app
        return OfflineProvider()
    return OfflineProvider()
