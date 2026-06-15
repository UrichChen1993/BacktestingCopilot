# src/backtesting_copilot/ml/dataset.py
"""Pure dataset construction for the regime classifier.

Turns a list of Bars into per-bar feature vectors and then into
(sequence-window, label) training samples. No torch dependency here so
these functions stay unit-testable offline.
"""

from __future__ import annotations

import numpy as np

from ..models import Bar
from .labeling import label_point

FEATURE_DIM = 4
_MA_WINDOW = 60
_ATR_WINDOW = 14


def bar_feature_matrix(bars: list[Bar]) -> list[list[float]]:
    """One [daily_return, range_pct, atr_ratio, ma_slope_ratio] row per bar."""
    closes = [b.close for b in bars]
    rows: list[list[float]] = []
    for i, bar in enumerate(bars):
        close = bar.close or 1.0
        ret = 0.0 if i == 0 or closes[i - 1] == 0 else closes[i] / closes[i - 1] - 1.0
        range_pct = (bar.high - bar.low) / close
        atr_ratio = _atr_ratio(bars, i, close)
        ma_slope_ratio = _ma_slope_ratio(closes, i, close)
        rows.append([ret, range_pct, atr_ratio, ma_slope_ratio])
    return rows


def _atr_ratio(bars: list[Bar], i: int, close: float) -> float:
    start = max(1, i - _ATR_WINDOW + 1)
    trs: list[float] = []
    for j in range(start, i + 1):
        prev_close = bars[j - 1].close
        trs.append(max(
            bars[j].high - bars[j].low,
            abs(bars[j].high - prev_close),
            abs(bars[j].low - prev_close),
        ))
    if not trs:
        return 0.0
    return float(np.mean(trs)) / close


def _ma_slope_ratio(closes: list[float], i: int, close: float) -> float:
    if i + 1 < _MA_WINDOW:
        return 0.0
    cur_ma = float(np.mean(closes[i - _MA_WINDOW + 1 : i + 1]))
    if i + 1 < _MA_WINDOW + 5:
        return 0.0
    prev_ma = float(np.mean(closes[i - _MA_WINDOW - 4 : i - 4]))
    return (cur_ma - prev_ma) / close


def build_sequences(
    bars: list[Bar],
    lookback: int,
    horizon: int,
    trend_thresh: float,
    min_osc: float,
) -> tuple[list[list[list[float]]], list[int]]:
    """Slide a lookback window; label by the last bar's forward outcome."""
    closes = [b.close for b in bars]
    matrix = bar_feature_matrix(bars)
    X: list[list[list[float]]] = []
    y: list[int] = []
    for t in range(lookback - 1, len(bars)):
        label = label_point(closes, t, horizon, trend_thresh, min_osc)
        if label is None:
            continue
        X.append(matrix[t - lookback + 1 : t + 1])
        y.append(label)
    return X, y
