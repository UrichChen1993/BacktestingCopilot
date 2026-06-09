"""Compute price/volatility/trend features from OHLCV bars (PRD §5.3.2, §5.4.2)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..models import Bar


@dataclass(frozen=True)
class PriceFeatures:
    last_close: float
    high_20: float
    low_20: float
    high_40: float
    low_40: float
    ma_60: float | None
    atr_14: float
    stdev_20: float
    range_pct_40: float  # (high_40 - low_40) / low_40
    ma_60_slope: float | None  # ma_60 - ma_60 N bars ago (proxy for slope)
    price_vs_ma60: float | None  # last_close / ma_60 - 1


def _atr(bars: list[Bar], window: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    for prev, cur in zip(bars[:-1], bars[1:]):
        tr = max(
            cur.high - cur.low,
            abs(cur.high - prev.close),
            abs(cur.low - prev.close),
        )
        trs.append(tr)
    window = min(window, len(trs))
    return float(np.mean(trs[-window:])) if trs else 0.0


def compute_features(bars: list[Bar], ma_window: int = 60, slope_lookback: int = 5) -> PriceFeatures:
    if not bars:
        raise ValueError("compute_features requires at least one bar")

    closes = np.array([b.close for b in bars], dtype=float)
    highs = np.array([b.high for b in bars], dtype=float)
    lows = np.array([b.low for b in bars], dtype=float)

    def window_high(n: int) -> float:
        return float(highs[-min(n, len(highs)):].max())

    def window_low(n: int) -> float:
        return float(lows[-min(n, len(lows)):].min())

    ma_60: float | None = None
    ma_60_slope: float | None = None
    price_vs_ma60: float | None = None
    if len(closes) >= ma_window:
        ma_60 = float(closes[-ma_window:].mean())
        if len(closes) >= ma_window + slope_lookback:
            prev_ma = float(closes[-ma_window - slope_lookback : -slope_lookback].mean())
            ma_60_slope = ma_60 - prev_ma
        price_vs_ma60 = float(closes[-1] / ma_60 - 1.0)

    low_40 = window_low(40)
    high_40 = window_high(40)
    range_pct_40 = (high_40 - low_40) / low_40 if low_40 else 0.0
    stdev_20 = float(np.std(closes[-min(20, len(closes)):], ddof=0))

    return PriceFeatures(
        last_close=float(closes[-1]),
        high_20=window_high(20),
        low_20=window_low(20),
        high_40=high_40,
        low_40=low_40,
        ma_60=ma_60,
        atr_14=_atr(bars, 14),
        stdev_20=stdev_20,
        range_pct_40=range_pct_40,
        ma_60_slope=ma_60_slope,
        price_vs_ma60=price_vs_ma60,
    )
