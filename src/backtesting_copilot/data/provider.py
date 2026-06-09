"""DataProvider interface.

All providers return a chronologically-sorted list of `Bar`. Fetch failures
must raise `DataUnavailableError` so the engine never produces signals from
missing data (PRD §9.2).
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..models import Bar


class DataUnavailableError(RuntimeError):
    """Raised when price/index data cannot be obtained or is incomplete."""


@runtime_checkable
class DataProvider(Protocol):
    def get_ohlcv(self, symbol: str, start: date, end: date) -> list[Bar]:
        """Return daily OHLCV bars for ``symbol`` within [start, end]."""
        ...

    def get_index_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        """Return daily bars for a market index (used by the 60MA filter)."""
        ...
