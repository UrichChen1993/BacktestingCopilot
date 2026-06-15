# RNN Regime Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pluggable, default-off RNN classifier that judges whether the current market is range-bound (grid-suitable), strengthening the strategy selection in `advisor.recommend_strategy`.

**Architecture:** A new `ml/` package holds rule-based auto-labeling, sequence dataset building, an LSTM model (optional `torch` import), a `RegimeClassifier` inference wrapper with a safe loader, and a CLI training script. The classifier is injected into `recommend_strategy` as an optional dependency; when absent (default, or `torch`/model missing) the advisor uses its existing statistical rule unchanged. The classifier never sets the price range — `price_lower/upper` still come from `features.low_40/high_40`.

**Tech Stack:** Python 3.12, numpy (existing), PyTorch (new, optional), pytest.

Spec: [docs/superpowers/specs/2026-06-15-rnn-regime-classifier-design.md](../specs/2026-06-15-rnn-regime-classifier-design.md)

---

## File Structure

- Create `src/backtesting_copilot/ml/__init__.py` — package exports
- Create `src/backtesting_copilot/ml/labeling.py` — pure rule-based labeling
- Create `src/backtesting_copilot/ml/dataset.py` — pure per-bar features + windowing
- Create `src/backtesting_copilot/ml/model.py` — LSTM definition (torch, optional)
- Create `src/backtesting_copilot/ml/classifier.py` — `RegimeClassifier` + safe loader
- Create `src/backtesting_copilot/ml/train.py` — CLI training + baseline report
- Modify `src/backtesting_copilot/ai/advisor.py` — optional classifier injection
- Create `tests/test_ml_labeling.py`
- Create `tests/test_ml_dataset.py`
- Create `tests/test_ml_classifier.py`
- Create `tests/test_advisor_regime.py`
- Modify `.gitignore` — ignore `artifacts/`

---

## Task 1: Rule-based auto-labeling

**Files:**
- Create: `src/backtesting_copilot/ml/__init__.py`
- Create: `src/backtesting_copilot/ml/labeling.py`
- Test: `tests/test_ml_labeling.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ml_labeling.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backtesting_copilot.ml'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/backtesting_copilot/ml/__init__.py
"""Experimental ML layer: RNN market-regime classifier (default-off)."""
```

```python
# src/backtesting_copilot/ml/labeling.py
"""Rule-based auto-labeling for the regime classifier.

A point t is labeled 1 ("range-bound, grid-suitable") when the next
`horizon` closes stay net-flat (small directional move) yet oscillate
enough to make grid trading worthwhile; otherwise 0. Returns None when
there is not enough future data.
"""

from __future__ import annotations


def label_point(
    closes: list[float],
    t: int,
    horizon: int,
    trend_thresh: float,
    min_osc: float,
) -> int | None:
    if t + horizon >= len(closes):
        return None
    base = closes[t]
    if base == 0:
        return None
    window = closes[t : t + horizon + 1]
    net = abs(closes[t + horizon] / base - 1.0)
    osc = (max(window) - min(window)) / base
    if net < trend_thresh and osc >= min_osc:
        return 1
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ml_labeling.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backtesting_copilot/ml/__init__.py src/backtesting_copilot/ml/labeling.py tests/test_ml_labeling.py
git commit -m "feat(ml): add rule-based regime auto-labeling"
```

---

## Task 2: Per-bar features + sequence windowing

**Files:**
- Create: `src/backtesting_copilot/ml/dataset.py`
- Test: `tests/test_ml_dataset.py`

`bar_feature_matrix` produces one feature vector per bar: `[daily_return, range_pct, atr_ratio, ma_slope_ratio]`. `build_sequences` slides a `lookback`-length window over those vectors and pairs each window with the label of its last bar.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ml_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` for `dataset`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ml_dataset.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backtesting_copilot/ml/dataset.py tests/test_ml_dataset.py
git commit -m "feat(ml): add per-bar features and sequence windowing"
```

---

## Task 3: LSTM model definition (optional torch)

**Files:**
- Create: `src/backtesting_copilot/ml/model.py`

No test here — the module only defines a torch `nn.Module` and a guarded import flag. It is exercised through Task 6 training and the smoke test in Task 4.

- [ ] **Step 1: Write the implementation**

```python
# src/backtesting_copilot/ml/model.py
"""LSTM regime classifier definition. Torch is an optional dependency:
import errors are swallowed so the rest of the package works offline.
"""

from __future__ import annotations

from .dataset import FEATURE_DIM

try:  # optional dependency
    import torch
    from torch import nn

    TORCH_AVAILABLE = True
except Exception:  # noqa: BLE001
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False


if TORCH_AVAILABLE:

    class RegimeLSTM(nn.Module):
        """Single-layer LSTM -> linear -> logit for P(range-bound)."""

        def __init__(self, input_dim: int = FEATURE_DIM, hidden_dim: int = 16):
            super().__init__()
            self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
            self.head = nn.Linear(hidden_dim, 1)

        def forward(self, x):  # x: (batch, seq, feat)
            out, _ = self.lstm(x)
            last = out[:, -1, :]
            return self.head(last).squeeze(-1)  # logits (batch,)

else:  # pragma: no cover - exercised only without torch installed

    class RegimeLSTM:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("PyTorch is not installed; RegimeLSTM unavailable.")
```

- [ ] **Step 2: Verify the module imports without torch breaking collection**

Run: `python -c "from backtesting_copilot.ml.model import TORCH_AVAILABLE; print(TORCH_AVAILABLE)"`
Expected: prints `True` or `False` (either is fine; no traceback)

- [ ] **Step 3: Commit**

```bash
git add src/backtesting_copilot/ml/model.py
git commit -m "feat(ml): add optional LSTM regime model definition"
```

---

## Task 4: RegimeClassifier inference wrapper + safe loader

**Files:**
- Create: `src/backtesting_copilot/ml/classifier.py`
- Test: `tests/test_ml_classifier.py`

`RegimeClassifier` wraps a callable scoring model and exposes `predict_proba(bars) -> float`. `maybe_load_classifier()` returns `None` unless all enable conditions hold, so the advisor can call it unconditionally.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ml_classifier.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ml_classifier.py -v`
Expected: FAIL with `ImportError` for `classifier`

- [ ] **Step 3: Write minimal implementation**

```python
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
            pad = [[0.0] * FEATURE_DIM] * (self.lookback - len(window))
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
    score_fn = _load_torch_score_fn(model_path)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ml_classifier.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backtesting_copilot/ml/classifier.py tests/test_ml_classifier.py
git commit -m "feat(ml): add RegimeClassifier wrapper and safe loader"
```

---

## Task 5: Inject classifier into the advisor

**Files:**
- Modify: `src/backtesting_copilot/ai/advisor.py`
- Test: `tests/test_advisor_regime.py`

When a classifier and bars are supplied, the advisor uses `p = predict_proba(bars)` in place of the `flat_trend` heuristic and maps `p` to confidence. When the classifier is `None` (default), behavior is identical to today.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_advisor_regime.py -v`
Expected: FAIL with `TypeError: recommend_strategy() got an unexpected keyword argument 'classifier'`

- [ ] **Step 3: Modify the implementation**

In `src/backtesting_copilot/ai/advisor.py`, change the signature and the GRID decision. Replace the current signature (lines ~31-37) and the `range_ok`/`flat_trend` block (lines ~46-64) with:

```python
def recommend_strategy(
    features: PriceFeatures,
    total_capital: float,
    *,
    provider: LLMProvider | None = None,
    market_below_ma: bool = False,
    classifier=None,  # ml.classifier.RegimeClassifier | None
    bars=None,        # list[Bar] | None, required when classifier is given
) -> StrategyRecommendation:
    provider = provider or OfflineProvider()
    reasons: list[str] = []
    risk_notes: list[str] = []

    slope_pct = None
    if features.ma_60 and features.ma_60_slope is not None and features.ma_60:
        slope_pct = features.ma_60_slope / features.ma_60

    range_ok = features.range_pct_40 >= MIN_RANGE_PCT_FOR_GRID

    regime_p = None
    if classifier is not None and bars:
        regime_p = classifier.predict_proba(bars)
        grid_suitable = regime_p >= 0.5
    else:
        grid_suitable = slope_pct is None or abs(slope_pct) <= RANGE_BOUND_MAX_SLOPE_PCT

    if range_ok and grid_suitable:
        strategy = StrategyType.GRID
        confidence = _grid_confidence(regime_p)
        if regime_p is not None:
            reasons.append(f"RNN 判定為區間盤（信心 {regime_p:.2f}）")
        else:
            reasons.append("近 40 日價格呈現區間震盪")
        reasons.append("波動率足以支撐網格交易")
        suggested = {
            "price_lower": round(features.low_40, 2),
            "price_upper": round(features.high_40, 2),
            "grid_num": 6 if features.range_pct_40 < 0.12 else 8,
            "total_capital": total_capital,
        }
        risk_notes.append("若跌破區間下緣，應暫停加碼")
        risk_notes.append("建議啟用 60MA 大盤濾網")
    else:
        strategy = StrategyType.VALUE_AVERAGING
        confidence = "MEDIUM" if not range_ok else "LOW"
        if regime_p is not None:
            reasons.append(f"RNN 判定偏趨勢盤（區間信心 {regime_p:.2f}），較適合分批布局")
        else:
            reasons.append("趨勢性較明顯或區間振幅不足，較適合分批布局")
        suggested = {
            "total_periods": 4,
            "period_interval_days": 14,
            "max_order_multiplier": 2,
            "negative_order_mode": "SKIP",
            "total_capital": total_capital,
        }
        risk_notes.append("連續下跌時價值平均可能快速消耗資金，保留單期上限")
```

Then add this helper above `recommend_strategy` (after the threshold constants):

```python
def _grid_confidence(regime_p: float | None) -> str:
    if regime_p is None:
        return "MEDIUM"
    if regime_p >= 0.7:
        return "HIGH"
    if regime_p >= 0.5:
        return "MEDIUM"
    return "LOW"
```

Leave the `if market_below_ma:` block and the `_narrate(...)`/return block at the end of the function unchanged.

- [ ] **Step 4: Run the new test and the existing scaffold test**

Run: `pytest tests/test_advisor_regime.py tests/test_scaffold.py -v`
Expected: PASS (all pass — `test_advisor_offline_recommends` still passes because default args preserve old behavior)

- [ ] **Step 5: Commit**

```bash
git add src/backtesting_copilot/ai/advisor.py tests/test_advisor_regime.py
git commit -m "feat(ai): inject optional RNN regime classifier into advisor"
```

---

## Task 6: Training CLI with baseline comparison

**Files:**
- Create: `src/backtesting_copilot/ml/train.py`
- Modify: `.gitignore`

No unit test (requires torch + data). Provides a runnable CLI that trains the LSTM, prints accuracy vs the existing slope rule, and saves the artifact.

- [ ] **Step 1: Add artifacts to .gitignore**

Append to `.gitignore`:

```
# Trained model artifacts (regenerated via ml/train.py)
artifacts/
```

- [ ] **Step 2: Write the training CLI**

```python
# src/backtesting_copilot/ml/train.py
"""CLI: train the regime LSTM and report accuracy vs the slope baseline.

Usage:
    python -m backtesting_copilot.ml.train --symbol 2330.TW \
        --start 2018-01-01 --end 2024-12-31 --epochs 20

Requires PyTorch. The deterministic pieces (labeling, dataset, advisor
integration) are covered by pytest; this script is for offline training.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from ..data.yfinance_provider import YFinanceProvider
from .classifier import DEFAULT_ARTIFACTS_DIR, DEFAULT_LOOKBACK, MODEL_FILENAME
from .dataset import build_sequences

DEFAULT_HORIZON = 20
DEFAULT_TREND_THRESH = 0.08
DEFAULT_MIN_OSC = 0.06


def _slope_baseline_pred(window: list[list[float]]) -> int:
    # ma_slope_ratio is the last feature column; flat slope -> predict range (1)
    last_slope = window[-1][3]
    return 1 if abs(last_slope) <= 0.03 else 0


def main(argv: list[str] | None = None) -> int:
    import torch
    from torch import nn

    from .model import RegimeLSTM

    parser = argparse.ArgumentParser(description="Train regime LSTM classifier")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(DEFAULT_ARTIFACTS_DIR))
    args = parser.parse_args(argv)

    torch.manual_seed(args.seed)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    bars = YFinanceProvider().get_ohlcv(args.symbol, start, end)
    X, y = build_sequences(
        bars, args.lookback, DEFAULT_HORIZON, DEFAULT_TREND_THRESH, DEFAULT_MIN_OSC
    )
    if not X:
        print("No training samples produced; widen the date range.")
        return 1

    split = int(len(X) * 0.8)
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32)
    X_tr, X_te = X_tensor[:split], X_tensor[split:]
    y_tr, y_te = y_tensor[:split], y_tensor[split:]

    model = RegimeLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()

    for epoch in range(args.epochs):
        model.train()
        opt.zero_grad()
        logits = model(X_tr)
        loss = loss_fn(logits, y_tr)
        loss.backward()
        opt.step()
        print(f"epoch {epoch + 1}/{args.epochs} loss={loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        preds = (torch.sigmoid(model(X_te)) >= 0.5).int()
    rnn_acc = float((preds == y_te.int()).float().mean())

    baseline_correct = sum(
        1 for w, label in zip(X[split:], y[split:]) if _slope_baseline_pred(w) == label
    )
    baseline_acc = baseline_correct / max(1, len(y[split:]))

    print(f"RNN test accuracy:      {rnn_acc:.3f}")
    print(f"Slope baseline accuracy: {baseline_acc:.3f}")
    if rnn_acc <= baseline_acc:
        print("WARNING: RNN did not beat the baseline — keep USE_RNN_REGIME off.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / MODEL_FILENAME)
    print(f"Saved model to {out_dir / MODEL_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify the CLI parses args without torch/data side effects**

Run: `python -m backtesting_copilot.ml.train --help`
Expected: prints usage text (argparse help), exit 0. (If torch is not installed, the `--help` path still works because the torch import is inside `main` after argparse only when invoked; if it errors on import, that is acceptable and documented — training requires torch.)

> Note: `YFinanceProvider().get_ohlcv(symbol, start: date, end: date)` is the verified data-layer API ([data/provider.py:22](../../../src/backtesting_copilot/data/provider.py#L22)). To train offline from a CSV instead, swap in `CsvProvider("data")`.

- [ ] **Step 4: Commit**

```bash
git add src/backtesting_copilot/ml/train.py .gitignore
git commit -m "feat(ml): add regime LSTM training CLI with baseline report"
```

---

## Task 7: Full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `pytest -q`
Expected: all tests pass, including the new `test_ml_*` and `test_advisor_regime` files and the unchanged existing suite.

- [ ] **Step 2: Confirm default-off behavior**

Run: `python -c "from backtesting_copilot.ml.classifier import maybe_load_classifier; print(maybe_load_classifier())"`
Expected: prints `None` (feature disabled by default).

---

## Self-Review Notes

- **Spec coverage:** §3 labeling → Task 1; §6 features/windowing → Task 2; §4 model → Task 3; §3 enable/fallback + §7 classifier wrapper → Task 4; §7 advisor integration → Task 5; §8 baseline + §10 params → Task 6; §8 test sweep → Task 7. `artifacts/` gitignore (§4) → Task 6 Step 1.
- **Data layer API:** Task 6 uses the verified `YFinanceProvider().get_ohlcv(symbol, start, end)` API; the deterministic, tested path (Tasks 1–5, 7) does not depend on the data layer at all.
- **Type consistency:** `RegimeClassifier(score_fn=..., lookback=...)`, `predict_proba(bars) -> float`, `maybe_load_classifier(artifacts_dir=..., lookback=...)`, `FEATURE_DIM = 4`, and `MODEL_FILENAME` are used consistently across Tasks 2, 4, 5, 6.
