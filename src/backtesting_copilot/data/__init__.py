"""Data access layer: OHLCV + market-index providers behind one interface."""

from .provider import DataProvider

__all__ = ["DataProvider"]
