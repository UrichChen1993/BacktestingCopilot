"""Tests for the regime classifier."""
from __future__ import annotations

from datetime import date

from backtesting_copilot.models import Bar
from backtesting_copilot.ml.classifier import RegimeClassifier, maybe_load_classifier


def _bars(n: int) -> list[Bar]:
    return [Bar(day=date(2026, 1, 1), open=100, high=101, low=99, close=100 + i, volume=1) for i in range(n)]


def test_predict_proba_uses_last_lookback_window():
    captured = {}

    def fake_score(window):  # window: list[list[float]]
        captured["len"] = len(window)
        return 0.73

    clf = RegimeClassifier(score_fn=fake_score, lookback=5)
    p = clf.predict_proba(_bars(20))
    assert p == 0.73
    assert captured["len"] == 5


def test_predict_proba_pads_when_too_few_bars():
    clf = RegimeClassifier(score_fn=lambda w: float(len(w)) / 100, lookback=10)
    # only 3 bars -> still produces a window of length 10 (left-padded)
    p = clf.predict_proba(_bars(3))
    assert p == 0.10


def test_maybe_load_disabled_returns_none(monkeypatch, tmp_path):
    monkeypatch.delenv("USE_RNN_REGIME", raising=False)
    assert maybe_load_classifier(artifacts_dir=tmp_path) is None


def test_maybe_load_missing_artifact_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_RNN_REGIME", "1")
    assert maybe_load_classifier(artifacts_dir=tmp_path) is None
