"""CSV-backed provider for offline / reproducible backtests.

Expects columns: date, open, high, low, close, volume. Index data may reuse
the same format (only close is needed for the MA filter).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from ..models import Bar
from .provider import DataUnavailableError

_REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def _load(path: Path, start: date, end: date) -> list[Bar]:
    if not path.exists():
        raise DataUnavailableError(f"CSV not found: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise DataUnavailableError(f"CSV {path} missing columns: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[(df["date"] >= start) & (df["date"] <= end)].sort_values("date")
    if df.empty:
        raise DataUnavailableError(f"No rows in {path} within {start}..{end}")
    return [
        Bar(
            day=row.date,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in df.itertuples(index=False)
    ]


class CsvProvider:
    """Reads bars from a directory of ``{symbol}.csv`` files."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    def _path(self, symbol: str) -> Path:
        return self.data_dir / f"{symbol}.csv"

    def get_ohlcv(self, symbol: str, start: date, end: date) -> list[Bar]:
        return _load(self._path(symbol), start, end)

    def get_index_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        return _load(self._path(symbol), start, end)
