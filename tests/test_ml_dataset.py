# tests/test_ml_dataset.py
from __future__ import annotations

from datetime import date

from backtesting_copilot.models import Bar
from backtesting_copilot.ml.dataset import FEATURE_DIM, bar_feature_matrix, build_sequences


def _bars(closes: list[float]) -> list[Bar]:
    return [
        Bar(day=date(2026, 1, 1) , open=c, high=c + 1, low=c - 1, close=c, volume=1000)
        if i == 0 else
        Bar(day=date(2026, 1, 1), open=c, high=c + 1, low=c - 1, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


def test_feature_matrix_shape():
    bars = _bars([100, 101, 102, 103, 104])
    mat = bar_feature_matrix(bars)
    assert len(mat) == len(bars)
    assert all(len(row) == FEATURE_DIM for row in mat)
    # first bar has no prior close -> zero return
    assert mat[0][0] == 0.0


def test_build_sequences_windows_and_labels():
    # 21 ascending closes -> trending -> all valid labels 0
    closes = [100 + i for i in range(21)]
    bars = _bars(closes)
    X, y = build_sequences(bars, lookback=3, horizon=5, trend_thresh=0.08, min_osc=0.06)
    # each X window is lookback x FEATURE_DIM
    assert all(len(w) == 3 and len(w[0]) == FEATURE_DIM for w in X)
    # samples need lookback history AND horizon future -> bounded count
    assert len(X) == len(y)
    assert len(X) > 0
    assert set(y) <= {0, 1}


def test_build_sequences_empty_when_too_short():
    bars = _bars([100, 101, 102])
    X, y = build_sequences(bars, lookback=3, horizon=5, trend_thresh=0.08, min_osc=0.06)
    assert X == [] and y == []
