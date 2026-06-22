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
    parser = argparse.ArgumentParser(description="Train regime LSTM classifier")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(DEFAULT_ARTIFACTS_DIR))
    args = parser.parse_args(argv)

    import torch
    from torch import nn

    from .model import RegimeLSTM

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
