"""Hard-rule risk engine (PRD §5.6).

Evaluated on every bar before any buy. Priority is higher than AI and the
strategy engine; nothing here can be disabled by the AI layer.
"""

from __future__ import annotations

from ..models import RiskCheck, StrategyStatus


class RiskEngine:
    def __init__(
        self,
        *,
        max_cash_usage_rate: float = 0.9,
        max_drawdown_limit: float = -0.10,
        market_filter_enabled: bool = True,
    ) -> None:
        self.max_cash_usage_rate = max_cash_usage_rate
        self.max_drawdown_limit = max_drawdown_limit
        self.market_filter_enabled = market_filter_enabled

    def evaluate(
        self,
        *,
        current_price: float,
        price_lower: float | None,
        used_capital: float,
        total_capital: float,
        current_drawdown: float,
        market_below_ma: bool,
        market_ma_slope_down: bool,
    ) -> RiskCheck:
        """Return what is allowed at this point in time.

        Rules (any may fire simultaneously):
          1. Market 60MA brake: index below MA *and* MA sloping down -> block buys.
          2. Below strategy band: price < price_lower -> stop new grid buys.
          3. Max cash usage: used/total >= limit -> stop new buys.
          4. Max drawdown: drawdown <= limit -> pause strategy.
        Selling / take-profit always stays allowed.
        """
        check = RiskCheck(allow_buy=True, allow_sell=True)

        # MARKET_60MA_BRAKE — 大盤指數低於 60MA 且 MA 向下斜，封鎖買入（整體市場太弱）
        if self.market_filter_enabled and market_below_ma and market_ma_slope_down:
            check.allow_buy = False
            check.triggered_rules.append("MARKET_60MA_BRAKE")
            check.new_status = StrategyStatus.PAUSED_BY_MARKET

        # BELOW_PRICE_LOWER — 當前價格低於策略下限（price_lower），停止網格補倉
        if price_lower is not None and current_price < price_lower:
            check.allow_buy = False
            check.triggered_rules.append("BELOW_PRICE_LOWER")

        # MAX_CASH_USAGE — 已用資金 / 總資金 ≥ 90%，資金不足，停止買入
        if total_capital > 0 and used_capital / total_capital >= self.max_cash_usage_rate:
            check.allow_buy = False
            check.triggered_rules.append("MAX_CASH_USAGE")

        # MAX_DRAWDOWN — 當前回撤 ≤ -10%，風險過高，封鎖買入並暫停策略（需人工確認是否繼續）
        if current_drawdown <= self.max_drawdown_limit:
            check.allow_buy = False
            check.triggered_rules.append("MAX_DRAWDOWN")
            check.new_status = StrategyStatus.PAUSED_BY_USER  # awaits manual confirm

        return check
