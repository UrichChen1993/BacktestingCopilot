"""Parameter validator: blocks unreasonable params before the engine (PRD §5.7)."""

from .parameter_validator import validate_config

__all__ = ["validate_config"]
