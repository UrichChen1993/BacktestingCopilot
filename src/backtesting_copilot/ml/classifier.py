# src/backtesting_copilot/ml/classifier.py
"""Inference wrapper + safe loader for the regime classifier.

`maybe_load_classifier` returns None unless the feature is explicitly
enabled, torch is installed, and a model artifact exists. The advisor can
therefore always call it and fall back transparently.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from ..models import Bar
from .dataset import FEATURE_DIM, bar_feature_matrix

DEFAULT_LOOKBACK = 40
DEFAULT_ARTIFACTS_DIR = Path("artifacts/regime")
MODEL_FILENAME = "regime_lstm.pt"

ScoreFn = Callable[[list[list[float]]], float]


class RegimeClassifier:
    """Scores a sequence of bars -> P(range-bound) in [0, 1]."""

    def __init__(self, score_fn: ScoreFn, lookback: int = DEFAULT_LOOKBACK):
        self._score_fn = score_fn
        self.lookback = lookback

    def _window(self, bars: list[Bar]) -> list[list[float]]:
        matrix = bar_feature_matrix(bars)
        window = matrix[-self.lookback :]
        if len(window) < self.lookback:
            pad = [[0.0] * FEATURE_DIM for _ in range(self.lookback - len(window))]
            window = pad + window
        return window

    def predict_proba(self, bars: list[Bar]) -> float:
        return float(self._score_fn(self._window(bars)))


def maybe_load_classifier(
    artifacts_dir: Path | None = None,
    lookback: int = DEFAULT_LOOKBACK,
) -> RegimeClassifier | None:
    if os.environ.get("USE_RNN_REGIME") != "1":
        return None
    artifacts_dir = Path(artifacts_dir) if artifacts_dir else DEFAULT_ARTIFACTS_DIR
    model_path = artifacts_dir / MODEL_FILENAME
    if not model_path.exists():
        return None
    try:
        from .model import TORCH_AVAILABLE
    except Exception:  # noqa: BLE001
        return None
    if not TORCH_AVAILABLE:
        return None
    try:
        score_fn = _load_torch_score_fn(model_path)
    except Exception:  # noqa: BLE001 - any load failure must fall back to None
        return None
    if score_fn is None:
        return None
    return RegimeClassifier(score_fn=score_fn, lookback=lookback)


def _load_torch_score_fn(model_path: Path) -> ScoreFn | None:  # pragma: no cover - needs torch + artifact
    import torch

    from .model import RegimeLSTM

    model = RegimeLSTM()
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()

    def score(window: list[list[float]]) -> float:
        with torch.no_grad():
            x = torch.tensor([window], dtype=torch.float32)
            logit = model(x)
            return float(torch.sigmoid(logit).item())

    return score
