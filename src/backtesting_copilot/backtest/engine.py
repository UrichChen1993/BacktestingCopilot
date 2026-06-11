"""Backtest engine: bar-by-bar event loop tying strategy + risk together.

Implements the daily-bar fill model from docs spec §5: grid levels fill against
the bar's low/high (conservative buy-before-sell ordering), value averaging fills
on schedule dates at the close, and the RiskEngine vetoes buys each bar.
"""

from __future__ import annotations

import logging

from ..data.provider import DataProvider
from ..models import (
    BacktestResult,
    GridStatus,
    Side,
    StrategyConfig,
    StrategyType,
    Trade,
)
from ..risk.engine import RiskEngine
from ..strategies.grid import generate_grid_levels, should_buy, should_sell
from ..strategies.value_averaging import build_va_schedule, order_size_for_period
from .metrics import max_drawdown, total_return, win_rate

logger = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(
        self,
        data_provider: DataProvider,
        risk_engine: RiskEngine | None = None,
        *,
        market_index_symbol: str = "^TWII",
        market_ma_window: int = 60,
    ) -> None:
        self.data_provider = data_provider
        self.risk_engine = risk_engine or RiskEngine()
        self.market_index_symbol = market_index_symbol
        self.market_ma_window = market_ma_window

    def run(self, config: StrategyConfig) -> BacktestResult:
        """Run a single-symbol, single-strategy historical backtest."""
        logger.info(
            "run: strategy=%s symbol=%s %s~%s market_filter=%s",
            config.strategy_type, config.symbol, config.start_date,
            config.end_date, config.market_filter_enabled,
        )
        bars = self.data_provider.get_ohlcv(config.symbol, config.start_date, config.end_date)
        logger.info("run: fetched %d bars for %s", len(bars), config.symbol)
        if config.strategy_type == StrategyType.GRID:
            return self._run_grid(config, bars)
        if config.strategy_type == StrategyType.VALUE_AVERAGING:
            return self._run_va(config, bars)
        raise NotImplementedError(f"strategy {config.strategy_type} not yet supported")

    # --- shared helpers ---------------------------------------------------

    def _index_closes(self, config: StrategyConfig) -> list:
        if not config.market_filter_enabled:
            return []
        closes = self.data_provider.get_index_closes(
            self.market_index_symbol, config.start_date, config.end_date
        )
        logger.info(
            "market filter on: loaded %d index bars (%s, ma_window=%d)",
            len(closes), self.market_index_symbol, self.market_ma_window,
        )
        return closes

    def _market_signals(self, index_closes: list, day) -> tuple[bool, bool]:
        """(below_ma, slope_down) for the index as of ``day``; (False, False)
        when there is not enough history for the moving average yet."""
        window = self.market_ma_window
        closes = [b.close for b in index_closes if b.day <= day]
        if len(closes) < window:
            return (False, False)
        ma = sum(closes[-window:]) / window
        below = closes[-1] < ma
        slope_down = False
        if len(closes) >= window + 1:
            prev_ma = sum(closes[-window - 1 : -1]) / window
            slope_down = (ma - prev_ma) < 0
        return (below, slope_down)

    def _evaluate_risk(self, config, *, cash, equity_curve, bar, index_closes, price_lower):
        below_ma, slope_down = self._market_signals(index_closes, bar.day)
        peak = max((v for _, v in equity_curve), default=config.total_capital)
        current_equity = equity_curve[-1][1] if equity_curve else config.total_capital
        current_drawdown = current_equity / peak - 1.0 if peak > 0 else 0.0
        return self.risk_engine.evaluate(
            current_price=bar.close,
            price_lower=price_lower,
            used_capital=config.total_capital - cash,
            total_capital=config.total_capital,
            current_drawdown=current_drawdown,
            market_below_ma=below_ma,
            market_ma_slope_down=slope_down,
        )

    # --- grid -------------------------------------------------------------

    def _run_grid(self, config: StrategyConfig, bars: list) -> BacktestResult:
        assert config.grid is not None
        levels = generate_grid_levels(config.grid, config.total_capital)
        logger.info(
            "_run_grid start: symbol=%s bars=%d levels=%d capital=%.2f",
            config.symbol, len(bars), len(levels), config.total_capital,
        )
        index_closes = self._index_closes(config)
        cash = config.total_capital
        trades: list[Trade] = []
        realized_profit = 0.0
        equity_curve: list[tuple] = []
        last_close = config.total_capital
        market_filter_count = 0

        for bar in bars:
            last_close = bar.close
            risk = self._evaluate_risk(
                config, cash=cash, equity_curve=equity_curve, bar=bar,
                index_closes=index_closes, price_lower=config.grid.price_lower,
            )
            logger.debug(
                "bar %s: O=%.2f H=%.2f L=%.2f C=%.2f cash=%.2f "
                "allow_buy=%s allow_sell=%s rules=%s",
                bar.day, bar.open, bar.high, bar.low, bar.close, cash,
                risk.allow_buy, risk.allow_sell, risk.triggered_rules,
            )
            if "MARKET_60MA_BRAKE" in risk.triggered_rules:
                market_filter_count += 1

            # BUY pass first (conservative ordering, docs spec §5).
            for level in levels:
                if not risk.allow_buy:
                    break
                if not should_buy(level, day_low=bar.low):
                    continue
                qty = int(level.unit_capital // level.buy_price)
                if qty <= 0:
                    continue
                cost = qty * level.buy_price
                fee = cost * config.fee_rate
                if cash < cost + fee:
                    continue
                cash -= cost + fee
                level.quantity = qty
                level.status = GridStatus.HOLDING
                logger.debug(
                    "BUY  L%d qty=%d @%.2f cost=%.2f fee=%.2f cash=%.2f",
                    level.level, qty, level.buy_price, cost, fee, cash,
                )
                trades.append(
                    Trade(
                        day=bar.day, side=Side.BUY, price=level.buy_price, quantity=qty,
                        amount=cost, fee=fee, tax=0.0,
                        reason=f"grid_buy L{level.level}",
                    )
                )

            # SELL pass (selling/take-profit always permitted by risk rules).
            for level in levels:
                if not risk.allow_sell:
                    break
                if not should_sell(level, day_high=bar.high):
                    continue
                qty = level.quantity
                proceeds = qty * level.sell_price
                fee = proceeds * config.fee_rate
                tax = proceeds * config.tax_rate
                buy_cost = qty * level.buy_price
                buy_fee = buy_cost * config.fee_rate
                pnl = proceeds - fee - tax - buy_cost - buy_fee
                cash += proceeds - fee - tax
                realized_profit += pnl
                level.realized_profit += pnl
                level.quantity = 0
                level.status = GridStatus.WAIT_BUY
                logger.debug(
                    "SELL L%d qty=%d @%.2f proceeds=%.2f pnl=%.2f cash=%.2f",
                    level.level, qty, level.sell_price, proceeds, pnl, cash,
                )
                trades.append(
                    Trade(
                        day=bar.day, side=Side.SELL, price=level.sell_price, quantity=qty,
                        amount=proceeds, fee=fee, tax=tax,
                        reason=f"grid_sell L{level.level};realized={pnl}",
                    )
                )

            holding_value = sum(l.quantity * bar.close for l in levels)
            equity_curve.append((bar.day, cash + holding_value))

        holding_qty = sum(l.quantity for l in levels)
        cost_basis = sum(l.quantity * l.buy_price for l in levels)
        logger.info(
            "_run_grid done: trades=%d realized=%.2f cash=%.2f holding_qty=%d "
            "market_filter_count=%d",
            len(trades), realized_profit, cash, holding_qty, market_filter_count,
        )
        return self._build_result(
            config, cash, trades, realized_profit, equity_curve, last_close,
            market_filter_count, holding_qty, cost_basis,
        )

    # --- value averaging --------------------------------------------------

    def _run_va(self, config: StrategyConfig, bars: list) -> BacktestResult:
        va = config.value_averaging
        assert va is not None
        schedule = build_va_schedule(va, config.total_capital, config.start_date)
        target_step = config.total_capital / va.total_periods
        logger.info(
            "_run_va start: symbol=%s bars=%d periods=%d capital=%.2f",
            config.symbol, len(bars), len(schedule), config.total_capital,
        )
        index_closes = self._index_closes(config)
        cash = config.total_capital
        holding_qty = 0
        cost_basis = 0.0
        trades: list[Trade] = []
        realized_profit = 0.0
        equity_curve: list[tuple] = []
        last_close = config.total_capital
        market_filter_count = 0
        next_period = 0

        for bar in bars:
            last_close = bar.close
            risk = self._evaluate_risk(
                config, cash=cash, equity_curve=equity_curve, bar=bar,
                index_closes=index_closes, price_lower=None,
            )
            logger.debug(
                "bar %s: C=%.2f cash=%.2f holding_qty=%d "
                "allow_buy=%s allow_sell=%s rules=%s",
                bar.day, bar.close, cash, holding_qty,
                risk.allow_buy, risk.allow_sell, risk.triggered_rules,
            )
            if "MARKET_60MA_BRAKE" in risk.triggered_rules:
                market_filter_count += 1

            # Execute every contribution period whose date has arrived (spec §5).
            while next_period < len(schedule) and schedule[next_period].execute_date <= bar.day:
                period = schedule[next_period]
                next_period += 1
                current_value = holding_qty * bar.close
                amount = order_size_for_period(
                    target_value=period.target_value,
                    current_value=current_value,
                    target_step=target_step,
                    max_order_multiplier=va.max_order_multiplier,
                    remaining_cash=cash,
                    negative_order_mode=va.negative_order_mode,
                )
                if amount <= 0 or not risk.allow_buy:
                    continue
                qty = int(amount // bar.close)
                if qty <= 0:
                    continue
                cost = qty * bar.close
                fee = cost * config.fee_rate
                if cash < cost + fee:
                    continue
                cash -= cost + fee
                holding_qty += qty
                cost_basis += cost
                logger.debug(
                    "BUY  P%d qty=%d @%.2f cost=%.2f fee=%.2f cash=%.2f holding_qty=%d",
                    period.period_index, qty, bar.close, cost, fee, cash, holding_qty,
                )
                trades.append(
                    Trade(
                        day=bar.day, side=Side.BUY, price=bar.close, quantity=qty,
                        amount=cost, fee=fee, tax=0.0,
                        reason=f"va_buy P{period.period_index}",
                    )
                )

            equity_curve.append((bar.day, cash + holding_qty * bar.close))

        logger.info(
            "_run_va done: trades=%d cash=%.2f holding_qty=%d market_filter_count=%d",
            len(trades), cash, holding_qty, market_filter_count,
        )
        return self._build_result(
            config, cash, trades, realized_profit, equity_curve, last_close,
            market_filter_count, holding_qty, cost_basis,
        )

    # --- result assembly --------------------------------------------------

    def _build_result(
        self, config, cash, trades, realized_profit, equity_curve, last_close,
        market_filter_count, holding_qty, cost_basis,
    ) -> BacktestResult:
        avg_cost = cost_basis / holding_qty if holding_qty else 0.0
        unrealized_profit = holding_qty * last_close - cost_basis
        final_value = cash + holding_qty * last_close
        used = config.total_capital - cash
        return BacktestResult(
            strategy_type=config.strategy_type,
            symbol=config.symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.total_capital,
            final_value=final_value,
            total_return=total_return(config.total_capital, final_value),
            mdd=max_drawdown([v for _, v in equity_curve]),
            realized_profit=realized_profit,
            unrealized_profit=unrealized_profit,
            trade_count=len(trades),
            win_rate=win_rate(trades),
            cash_usage_rate=used / config.total_capital if config.total_capital else 0.0,
            remaining_cash=cash,
            holding_quantity=holding_qty,
            avg_cost=avg_cost,
            market_filter_count=market_filter_count,
            trades=trades,
            equity_curve=equity_curve,
        )
