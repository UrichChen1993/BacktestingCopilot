"""yfinance-backed provider (default online source for the V1 MVP).

Network/parse failures surface as DataUnavailableError so the engine can
refuse to trade on bad data (PRD §9.2).
"""

from __future__ import annotations

from datetime import date, timedelta

from ..models import Bar
from .provider import DataUnavailableError


def _fetch(symbol: str, start: date, end: date) -> list[Bar]:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DataUnavailableError("yfinance not installed") from exc

    # yfinance end is exclusive; pad by a day to include `end`.
    try:
        df = yf.download(
            symbol,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            progress=False,
        )
    except Exception as exc:  # noqa: BLE001 - any fetch error is "unavailable"
        raise DataUnavailableError(f"yfinance fetch failed for {symbol}: {exc}") from exc

    if df is None or df.empty:
        raise DataUnavailableError(f"yfinance returned no data for {symbol}")

    # Flatten possible MultiIndex columns (single-ticker downloads).
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    bars: list[Bar] = []
    for idx, row in df.iterrows():
        bars.append(
            Bar(
                day=idx.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    if not bars:
        raise DataUnavailableError(f"yfinance produced no usable bars for {symbol}")
    return bars


class YFinanceProvider:
    def get_ohlcv(self, symbol: str, start: date, end: date) -> list[Bar]:
        return _fetch(symbol, start, end)

    def get_index_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        return _fetch(symbol, start, end)
