"""AI layer: switchable LLM providers + advisor/suggester/analyst.

AI only analyses, suggests and explains. It never writes config directly,
never bypasses risk, never trades without user confirmation (PRD §3.2).
"""

from .provider import LLMProvider, OfflineProvider, get_provider

__all__ = ["LLMProvider", "OfflineProvider", "get_provider"]
