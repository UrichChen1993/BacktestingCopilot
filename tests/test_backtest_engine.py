"""TDD coverage for the bar-by-bar BacktestEngine event loop (docs spec §5/§9).

Uses a real in-memory DataProvider (not a mock) so the loop is exercised
against actual Bar objects exactly as the CSV/yfinance providers would supply.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backtesting_copilot.backtest.engine import BacktestEngine
from backtesting_copilot.data.csv_provider import CsvProvider
from backtesting_copilot.risk.engine import RiskEngine
from backtesting_copilot.models import (
    Bar,
    GridParams,
    StrategyConfig,
    StrategyType,
    ValueAveragingParams,
)


class ListProvider:
    """In-memory DataProvider returning canned bars (satisfies the Protocol)."""

    def __init__(self, ohlcv: list[Bar], index: list[Bar] | None = None) -> None:
        self._ohlcv = ohlcv
        self._index = index or []

    def get_ohlcv(self, symbol: str, start: date, end: date) -> list[Bar]:
        return [b for b in self._ohlcv if start <= b.day <= end]

    def get_index_closes(self, symbol: str, start: date, end: date) -> list[Bar]:
        return [b for b in self._index if start <= b.day <= end]


def _bar(d: date, o: float, h: float, low: float, c: float, v: float = 1000) -> Bar:
    return Bar(day=d, open=o, high=h, low=low, close=c, volume=v)


def _grid_config(**overrides) -> StrategyConfig:
    base = dict(
        symbol="X",
        strategy_type=StrategyType.GRID,
        total_capital=20000,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        fee_rate=0.0,
        tax_rate=0.0,
        market_filter_enabled=False,
        grid=GridParams(price_lower=100, price_upper=104, grid_num=2),
    )
    base.update(overrides)
    return StrategyConfig(**base)


# --- grid: structural baseline -------------------------------------------

def test_flat_run_above_band_makes_no_trades():
    """Price stays at 105 (above the grid band) so nothing ever fills."""
    bars = [_bar(date(2026, 1, 1 + i), 105, 105, 105, 105) for i in range(5)]
    result = BacktestEngine(ListProvider(bars)).run(_grid_config())

    assert result.trade_count == 0
    assert result.holding_quantity == 0
    assert result.final_value == pytest.approx(20000)
    assert result.remaining_cash == pytest.approx(20000)
    assert result.total_return == pytest.approx(0.0)


def test_single_dip_fills_one_grid_buy():
    """Low touches 102 -> L2 buys at 102; price then holds below 104 (no sell)."""
    bars = [
        _bar(date(2026, 1, 1), 105, 105, 105, 105),  # above band, no fill
        _bar(date(2026, 1, 2), 101, 101, 101, 101),  # low<=102 -> buy L2 @102
        _bar(date(2026, 1, 3), 103, 103, 103, 103),  # high<104 -> no sell; close 103
    ]
    result = BacktestEngine(ListProvider(bars)).run(_grid_config())

    # unit_capital = 20000/2 = 10000; qty = floor(10000/102) = 98; cost = 9996
    assert result.trade_count == 1
    assert result.holding_quantity == 98
    assert result.remaining_cash == pytest.approx(10004)
    assert result.avg_cost == pytest.approx(102)
    # marked at the last close of 103: holdings 98*103 = 10094
    assert result.final_value == pytest.approx(10004 + 98 * 103)
    assert result.unrealized_profit == pytest.approx(98 * (103 - 102))
    assert result.realized_profit == pytest.approx(0.0)


def test_buy_then_sell_realizes_profit():
    """Deep dip fills both levels, then a rally sells both for realized gain."""
    bars = [
        # low touches 100 (the floor, not below it) -> buy L1@100 & L2@102; close 100
        # keeps the risk BELOW_PRICE_LOWER rule from vetoing.
        _bar(date(2026, 1, 1), 100, 100, 100, 100),
        _bar(date(2026, 1, 2), 105, 105, 105, 105),  # high>=102 & >=104 -> sell both
    ]
    result = BacktestEngine(ListProvider(bars)).run(_grid_config())

    # buys: 100@100 (=10000) + 98@102 (=9996); sells: 100@102 + 98@104
    # realized = (10200-10000) + (10192-9996) = 200 + 196 = 396
    assert result.trade_count == 4
    assert result.holding_quantity == 0
    assert result.realized_profit == pytest.approx(396)
    assert result.remaining_cash == pytest.approx(20396)
    assert result.final_value == pytest.approx(20396)
    assert result.win_rate == pytest.approx(1.0)
    assert result.total_return == pytest.approx(396 / 20000)


def test_fees_and_taxes_feed_realized_profit():
    """Spec §5: buy fee + sell fee + tax all count toward realized P&L, so a
    fully-closed book satisfies realized_profit == final_value - initial."""
    config = _grid_config(fee_rate=0.001425, tax_rate=0.003)
    bars = [
        _bar(date(2026, 1, 1), 101, 101, 101, 101),  # low<=102 (not <=100) -> buy only L2@102
        _bar(date(2026, 1, 2), 104, 104, 104, 104),  # high>=104 -> sell L2@104
    ]
    result = BacktestEngine(ListProvider(bars)).run(config)

    # qty=floor(10000/102)=98; buy 98@102, sell 98@104
    # buy_fee=9996*0.001425; sell_fee=10192*0.001425; tax=10192*0.003
    expected_pnl = (10192 - 10192 * 0.001425 - 10192 * 0.003) - (9996 + 9996 * 0.001425)
    assert result.trade_count == 2
    assert result.holding_quantity == 0
    assert result.realized_profit == pytest.approx(expected_pnl)
    # invariant: when flat, all P&L is realized and equals the cash delta
    assert result.realized_profit == pytest.approx(result.final_value - config.total_capital)


# --- risk integration -----------------------------------------------------

def test_market_brake_blocks_grid_buy():
    """Index drops below its MA with a downward slope -> buys are vetoed."""
    stock = [
        _bar(date(2026, 1, 1), 105, 105, 105, 105),
        _bar(date(2026, 1, 2), 105, 105, 105, 105),
        _bar(date(2026, 1, 3), 105, 105, 105, 105),
        _bar(date(2026, 1, 4), 105, 105, 105, 105),
        _bar(date(2026, 1, 5), 101, 101, 101, 101),  # dip would buy L2@102...
    ]
    # flat index then a sharp drop on day5: MA3=98, close 94<98, slope -2 -> brake
    index = [
        _bar(date(2026, 1, 1), 100, 100, 100, 100),
        _bar(date(2026, 1, 2), 100, 100, 100, 100),
        _bar(date(2026, 1, 3), 100, 100, 100, 100),
        _bar(date(2026, 1, 4), 100, 100, 100, 100),
        _bar(date(2026, 1, 5), 94, 94, 94, 94),
    ]
    provider = ListProvider(stock, index)
    config = _grid_config(market_filter_enabled=True)
    result = BacktestEngine(provider, market_ma_window=3).run(config)

    assert result.trade_count == 0      # ...but the brake vetoes the buy
    assert result.holding_quantity == 0
    assert result.market_filter_count == 1


# --- value averaging ------------------------------------------------------

def _va_config(**overrides) -> StrategyConfig:
    base = dict(
        symbol="X",
        strategy_type=StrategyType.VALUE_AVERAGING,
        total_capital=100000,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 4),
        fee_rate=0.0,
        tax_rate=0.0,
        market_filter_enabled=False,
        value_averaging=ValueAveragingParams(total_periods=4, period_interval_days=1),
    )
    base.update(overrides)
    return StrategyConfig(**base)


def test_value_averaging_accumulates_to_target():
    """At a flat price each period invests exactly one target step (25000)."""
    bars = [_bar(date(2026, 1, 1 + i), 100, 100, 100, 100) for i in range(4)]
    result = BacktestEngine(ListProvider(bars)).run(_va_config())

    # target_step = 100000/4 = 25000; qty per period = 25000/100 = 250
    assert result.trade_count == 4
    assert result.holding_quantity == 1000
    assert result.remaining_cash == pytest.approx(0)
    assert result.avg_cost == pytest.approx(100)
    assert result.final_value == pytest.approx(100000)
    assert result.unrealized_profit == pytest.approx(0)


def test_value_averaging_buys_more_when_price_drops():
    """When the price halves, period 2 must invest extra to reach its target."""
    bars = [
        _bar(date(2026, 1, 1), 100, 100, 100, 100),  # P1: invest 25000 -> 250 sh
        _bar(date(2026, 1, 2), 50, 50, 50, 50),      # P2: holdings worth 12500,
        # target 50000 -> invest 37500 (under cap 50000) -> 750 sh
    ]
    result = BacktestEngine(ListProvider(bars)).run(_va_config())

    assert result.trade_count == 2
    assert result.holding_quantity == 1000
    assert result.remaining_cash == pytest.approx(37500)
    assert result.avg_cost == pytest.approx(62.5)  # (25000 + 37500) / 1000


def test_max_cash_usage_blocks_further_va_buys():
    """Engine computes used_capital from its own state; once it crosses the
    risk limit, scheduled VA buys stop. VA isolates this from price-position
    rules (price_lower is None). Limit tightened to 0.5 so the gate lands on
    a clean period boundary at a flat price."""
    bars = [_bar(date(2026, 1, 1 + i), 100, 100, 100, 100) for i in range(4)]
    engine = BacktestEngine(ListProvider(bars), RiskEngine(max_cash_usage_rate=0.5))
    result = engine.run(_va_config())

    # P1 invest 25000 (used 25%), P2 invest 25000 (used 50%);
    # P3/P4 start at used>=50% -> MAX_CASH_USAGE vetoes them.
    assert result.trade_count == 2
    assert result.holding_quantity == 500
    assert result.remaining_cash == pytest.approx(50000)


def test_max_drawdown_pauses_va_buys():
    """A >10% equity drawdown (default limit) vetoes the next scheduled buy.
    Drawdown is engine-computed from the running equity curve."""
    bars = [
        _bar(date(2026, 1, 1), 100, 100, 100, 100),  # P1: buy 250 @100, equity 100000 (peak)
        _bar(date(2026, 1, 2), 55, 55, 55, 55),       # P2: catch-up buy; equity ends 88750
        _bar(date(2026, 1, 3), 55, 55, 55, 55),       # P3 start dd=-11.25% -> blocked
    ]
    result = BacktestEngine(ListProvider(bars)).run(_va_config())

    # only P1 and P2 fill; P3's scheduled buy is paused by the drawdown rule
    assert result.trade_count == 2
    assert result.holding_quantity == 909  # 250 + floor(36250/55)=659
    assert result.mdd <= -0.10


# --- end-to-end through the real CsvProvider ------------------------------

def test_grid_backtest_end_to_end_via_csv_provider():
    """Full data->engine->metrics path against an on-disk fixture CSV (spec §9)."""
    provider = CsvProvider(Path(__file__).parent / "fixtures")
    config = _grid_config(symbol="E2E")
    result = BacktestEngine(provider).run(config)

    # day1 low 100 buys L1@100 & L2@102; day2 high 105 sells both -> realized 396
    assert result.trade_count == 4
    assert result.holding_quantity == 0
    assert result.realized_profit == pytest.approx(396)
    assert result.final_value == pytest.approx(20396)
    assert len(result.equity_curve) == 2
