# tests/test_ml_labeling.py
from __future__ import annotations

from backtesting_copilot.ml.labeling import label_point


def test_range_bound_is_label_1():
    # oscillates within a band, no net trend over the horizon
    closes = [100, 106, 100, 107, 101, 106, 100, 107, 100, 106, 101]
    # horizon=10: start 100, end 101 -> net ~1%, osc ~7%
    assert label_point(closes, t=0, horizon=10, trend_thresh=0.08, min_osc=0.06) == 1


def test_strong_trend_is_label_0():
    closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120]
    # net move 20% over horizon -> trending
    assert label_point(closes, t=0, horizon=10, trend_thresh=0.08, min_osc=0.06) == 0


def test_low_oscillation_is_label_0():
    closes = [100, 100.5, 100, 100.5, 100, 100.5, 100, 100.5, 100, 100.5, 100]
    # net ~0 but osc only ~0.5% < min_osc -> not grid-suitable
    assert label_point(closes, t=0, horizon=10, trend_thresh=0.08, min_osc=0.06) == 0


def test_insufficient_future_returns_none():
    closes = [100, 101, 102]
    assert label_point(closes, t=0, horizon=10, trend_thresh=0.08, min_osc=0.06) is None
