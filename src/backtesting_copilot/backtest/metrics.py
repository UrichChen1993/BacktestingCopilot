"""Performance metric formulas (PRD §6.3). Pure functions, fully unit-testable."""

from __future__ import annotations

from ..models import Side, Trade


def total_return(initial_capital: float, final_value: float) -> float:
    # 防禦式檢查：本金小於等於 0 時，報酬率公式沒有意義。
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    return final_value / initial_capital - 1.0


def max_drawdown(equity_curve: list[float]) -> float:
    """Largest peak-to-trough drop as a negative fraction (0.0 if none)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for value in equity_curve:
        # peak 記錄目前看過的歷史最高淨值。
        peak = max(peak, value)
        if peak > 0:
            # value / peak - 1 是從高點跌下來的比例；mdd 保留最糟的一次。
            mdd = min(mdd, value / peak - 1.0)
    return mdd


def win_rate(trades: list[Trade]) -> float:
    """Fraction of closing (SELL) trades with positive realized profit.

    Realized profit is encoded in the SELL trade's ``reason`` is not reliable,
    so the engine should pass realized pnl; here we approximate using sells
    that report positive amounts via the trade ledger pairing done upstream.
    """
    sells = [t for t in trades if t.side == Side.SELL]
    if not sells:
        return 0.0
    wins = sum(1 for t in sells if _realized(t) > 0)
    return wins / len(sells)


def _realized(trade: Trade) -> float:
    # The engine stores realized pnl in `reason` as "realized=<value>" when known.
    marker = "realized="
    if trade.reason and marker in trade.reason:
        try:
            return float(trade.reason.split(marker, 1)[1].split(";", 1)[0])
        except ValueError:
            return 0.0
    return 0.0
