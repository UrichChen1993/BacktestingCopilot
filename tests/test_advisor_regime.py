# tests/test_advisor_regime.py
from __future__ import annotations

from datetime import date

from backtesting_copilot.features.price_features import compute_features
from backtesting_copilot.ml.classifier import RegimeClassifier
from backtesting_copilot.models import Bar, StrategyType
from backtesting_copilot.ai.advisor import recommend_strategy


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
    assert rec.recommended_strategy in (StrategyType.GRID, StrategyType.VALUE_AVERAGING)
    assert rec.reason
