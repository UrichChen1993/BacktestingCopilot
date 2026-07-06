# tests/test_advisor_regime.py
from __future__ import annotations

from datetime import date

import pytest

from backtesting_copilot.features.price_features import compute_features
from backtesting_copilot.ml.classifier import RegimeClassifier
from backtesting_copilot.models import Bar, StrategyType
from backtesting_copilot.ai.advisor import recommend_strategy, _grid_confidence


def _bars(closes: list[float]) -> list[Bar]:
    return [Bar(day=date(2026, 1, 1), open=c, high=c + 1, low=c - 1, close=c, volume=1000) for c in closes]


# enough amplitude so range_ok is True regardless of the classifier
_RANGEY = [100, 110, 100, 111, 101, 110, 100, 112, 101, 110]


def test_high_proba_selects_grid_with_high_confidence():
    bars = _bars(_RANGEY)
    feats = compute_features(bars)
    clf = RegimeClassifier(score_fn=lambda w: 0.9, lookback=5)
    rec = recommend_strategy(feats, 100000, classifier=clf, bars=bars)
    assert rec.recommended_strategy == StrategyType.GRID
    assert rec.confidence_level == "HIGH"


def test_low_proba_avoids_grid():
    bars = _bars(_RANGEY)
    feats = compute_features(bars)
    clf = RegimeClassifier(score_fn=lambda w: 0.1, lookback=5)
    rec = recommend_strategy(feats, 100000, classifier=clf, bars=bars)
    assert rec.recommended_strategy == StrategyType.VALUE_AVERAGING


def test_none_classifier_keeps_existing_behavior():
    bars = _bars(_RANGEY)
    feats = compute_features(bars)
    rec = recommend_strategy(feats, 100000)
    assert rec.recommended_strategy == StrategyType.GRID
    assert rec.confidence_level == "MEDIUM"
    assert rec.reason


_FILTER_NOTE = "建議啟用 60MA 大盤濾網"


def test_grid_suggests_market_filter_when_disabled():
    feats = compute_features(_bars(_RANGEY))
    rec = recommend_strategy(feats, 100000, market_filter_enabled=False)
    assert rec.recommended_strategy == StrategyType.GRID
    assert _FILTER_NOTE in rec.risk_notes


def test_grid_omits_market_filter_note_when_already_enabled():
    feats = compute_features(_bars(_RANGEY))
    rec = recommend_strategy(feats, 100000, market_filter_enabled=True)
    assert rec.recommended_strategy == StrategyType.GRID
    assert _FILTER_NOTE not in rec.risk_notes


@pytest.mark.parametrize(
    "p, expected",
    [(None, "MEDIUM"), (0.7, "HIGH"), (0.69, "MEDIUM"), (0.5, "MEDIUM"), (0.499, "LOW")],
)
def test_grid_confidence_thresholds(p, expected):
    assert _grid_confidence(p) == expected


def test_classifier_without_bars_raises():
    feats = compute_features(_bars(_RANGEY))
    clf = RegimeClassifier(score_fn=lambda w: 0.9, lookback=5)
    with pytest.raises(ValueError):
        recommend_strategy(feats, 100000, classifier=clf)
