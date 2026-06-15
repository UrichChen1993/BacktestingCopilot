"""DataProvider interface.

All providers return a chronologically-sorted list of `Bar`. Fetch failures
must raise `DataUnavailableError` so the engine never produces signals from
missing data (PRD §9.2).

學習重點：Protocol 是 Python 的「介面」寫法。只要一個類別長得像
DataProvider（有這兩個方法），就可以被 BacktestEngine 使用。
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..models import Bar


class DataUnavailableError(RuntimeError):
    """Raised when price/index data cannot be obtained or is incomplete."""


@runtime_checkable
class DataProvider(Protocol):
    # Protocol 裡通常只放方法簽名，不放實作；真正實作在 csv/yfinance provider。
    def get_ohlcv(self, symbol: str, start: date, end: date) -> list[Bar]:
        """Return daily OHLCV bars for ``symbol`` within [start, end]."""
        ...

    def get_index_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        """Return daily bars for a market index (used by the 60MA filter)."""
        ...
