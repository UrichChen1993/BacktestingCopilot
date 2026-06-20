from __future__ import annotations
from backtesting_copilot.data.provider import DataUnavailableError


class APIValidationError(Exception):
    """Raised by routers when parameter validation fails."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


def classify_exception(exc: Exception) -> tuple[int, dict]:
    if isinstance(exc, DataUnavailableError):
        return 422, {"detail": str(exc), "error_code": "DATA_UNAVAILABLE"}
    if isinstance(exc, APIValidationError):
        return 400, {"detail": str(exc), "error_code": "VALIDATION_ERROR"}
    if isinstance(exc, (ValueError, TypeError)):
        return 400, {"detail": str(exc), "error_code": "VALIDATION_ERROR"}
    return 500, {"detail": str(exc), "error_code": "INTERNAL_ERROR"}
