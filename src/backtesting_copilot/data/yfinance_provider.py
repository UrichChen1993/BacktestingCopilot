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
        # 延遲 import：只有真的使用 yfinance provider 時才需要這個套件。
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DataUnavailableError("yfinance not installed") from exc

    # yfinance 的 end 是「不包含」結束日，所以多加一天才會含 end 當天。
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

    # yfinance 有時會回傳多層欄位；單一 ticker 只需要第一層欄名。
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    bars: list[Bar] = []
    for idx, row in df.iterrows():
        # 外部套件的資料格式進來後，立刻轉成內部 Bar 模型；
        # 後面的策略/風控就不用知道 yfinance 的欄位細節。
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
