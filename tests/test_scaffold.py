"""Smoke + unit tests for the implemented (deterministic) scaffold pieces.

The backtest event loop is pending TDD; these lock down the pure building
blocks it will compose.
"""

from __future__ import annotations

from datetime import date

import pytest

from backtesting_copilot.ai.analyst import analyze_backtest
from backtesting_copilot.ai.advisor import recommend_strategy
from backtesting_copilot.backtest.metrics import max_drawdown, total_return
from backtesting_copilot.features.price_features import compute_features
from backtesting_copilot.models import (
    Bar,
    BacktestResult,
    GridParams,
    GridStatus,
    NegativeOrderMode,
    StrategyConfig,
    StrategyType,
    ValueAveragingParams,
)
from backtesting_copilot.risk.engine import RiskEngine
from backtesting_copilot.strategies.grid import generate_grid_levels, should_buy, should_sell
from backtesting_copilot.strategies.value_averaging import (
    build_va_schedule,
    order_size_for_period,
)
from backtesting_copilot.validator import validate_config


def _bars(closes: list[float]) -> list[Bar]:
    return [
        Bar(day=date(2026, 1, 1 + i), open=c, high=c + 1, low=c - 1, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


# --- grid -----------------------------------------------------------------

def test_generate_grid_levels_matches_prd_example():
    params = GridParams(price_lower=100, price_upper=112, grid_num=6)
    levels = generate_grid_levels(params, total_capital=100000)
    assert [l.buy_price for l in levels] == [100, 102, 104, 106, 108, 110]
    assert [l.sell_price for l in levels] == [102, 104, 106, 108, 110, 112]
    assert levels[0].unit_capital == pytest.approx(100000 / 6)


def test_grid_triggers():
    params = GridParams(price_lower=100, price_upper=112, grid_num=6)
    level = generate_grid_levels(params, 100000)[0]
    assert should_buy(level, day_low=99) is True
    level.status = GridStatus.HOLDING
    assert should_sell(level, day_high=103) is True
    assert should_buy(level, day_low=99) is False  # not WAIT_BUY anymore


# --- value averaging ------------------------------------------------------

def test_va_schedule_targets():
    params = ValueAveragingParams(total_periods=4, period_interval_days=14)
    sched = build_va_schedule(params, total_capital=100000, start_date=date(2026, 6, 1))
    assert [p.target_value for p in sched] == [25000, 50000, 75000, 100000]
    assert sched[1].execute_date == date(2026, 6, 15)


def test_va_order_size_caps_and_skip():
    # raw 40000 capped to step*multiplier = 25000*2 = 50000, then remaining cash 30000
    amount = order_size_for_period(
        target_value=40000, current_value=0, target_step=25000,
        max_order_multiplier=2, remaining_cash=30000,
        negative_order_mode=NegativeOrderMode.SKIP,
    )
    assert amount == 30000
    # negative raw with SKIP => 0
    assert order_size_for_period(
        target_value=20000, current_value=30000, target_step=25000,
        max_order_multiplier=2, remaining_cash=99999,
        negative_order_mode=NegativeOrderMode.SKIP,
    ) == 0.0


# --- validator ------------------------------------------------------------

def test_validator_rejects_grid_num_over_limit():
    config = StrategyConfig(
        symbol="2330.TW", strategy_type=StrategyType.GRID, total_capital=100000,
        start_date=date(2026, 6, 1), end_date=date(2026, 7, 31),
        grid=GridParams(price_lower=100, price_upper=112, grid_num=20),
    )
    res = validate_config(config)
    assert res.valid is False
    assert res.suggested_fix.get("grid_num") == 12


def test_validator_passes_reasonable_grid():
    config = StrategyConfig(
        symbol="2330.TW", strategy_type=StrategyType.GRID, total_capital=100000,
        start_date=date(2026, 6, 1), end_date=date(2026, 7, 31),
        grid=GridParams(price_lower=100, price_upper=112, grid_num=6),
    )
    assert validate_config(config).valid is True


# --- metrics --------------------------------------------------------------

def test_total_return_and_mdd():
    assert total_return(100000, 103200) == pytest.approx(0.032)
    assert max_drawdown([100, 120, 90, 110]) == pytest.approx(90 / 120 - 1)


# --- features -------------------------------------------------------------

def test_compute_features_basic():
    feats = compute_features(_bars([100, 102, 101, 103, 105]))
    assert feats.last_close == 105
    assert feats.high_20 == 106  # max high = 105+1
    assert feats.atr_14 > 0


# --- risk -----------------------------------------------------------------

def test_risk_market_brake_blocks_buy():
    engine = RiskEngine()
    check = engine.evaluate(
        current_price=105, price_lower=100, used_capital=0, total_capital=100000,
        current_drawdown=0.0, market_below_ma=True, market_ma_slope_down=True,
    )
    assert check.allow_buy is False
    assert check.allow_sell is True
    assert "MARKET_60MA_BRAKE" in check.triggered_rules


def test_risk_max_cash_usage():
    engine = RiskEngine()
    check = engine.evaluate(
        current_price=105, price_lower=100, used_capital=95000, total_capital=100000,
        current_drawdown=0.0, market_below_ma=False, market_ma_slope_down=False,
    )
    assert check.allow_buy is False
    assert "MAX_CASH_USAGE" in check.triggered_rules


# --- AI (offline) ---------------------------------------------------------

def test_advisor_offline_recommends():
    feats = compute_features(_bars([100, 108, 101, 110, 102, 109, 103, 111]))
    rec = recommend_strategy(feats, total_capital=100000)
    assert rec.recommended_strategy in (StrategyType.GRID, StrategyType.VALUE_AVERAGING)
    assert rec.reason


def test_analyst_offline_report():
    result = BacktestResult(
        strategy_type=StrategyType.GRID, symbol="2330.TW",
        start_date=date(2026, 4, 1), end_date=date(2026, 5, 31),
        initial_capital=100000, final_value=103200, total_return=0.032, mdd=-0.085,
        realized_profit=1800, unrealized_profit=-3200, trade_count=18, win_rate=0.64,
        cash_usage_rate=0.82, remaining_cash=18000, holding_quantity=100, avg_cost=101.0,
        market_filter_count=1,
    )
    report = analyze_backtest(result)
    assert "3.2%" in report.summary
    assert report.suggestions
    assert report.risk_level in ("LOW", "MEDIUM", "HIGH")
