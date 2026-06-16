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
