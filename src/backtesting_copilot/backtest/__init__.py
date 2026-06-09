"""Backtest engine and performance metrics (PRD §6)."""

from .metrics import max_drawdown, total_return, win_rate

__all__ = ["max_drawdown", "total_return", "win_rate"]
