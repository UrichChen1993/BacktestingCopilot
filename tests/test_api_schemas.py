import pytest
from backtesting_copilot.app.api.schemas import BacktestRequest, OptimizeRequest, AdvisorRequest


def test_backtest_request_grid_valid():
    req = BacktestRequest(
        symbol="2330.TW",
        strategy_type="grid",
        total_capital=100000,
        start_date="2026-04-01",
        end_date="2026-05-31",
        market_filter_enabled=True,
        llm_provider="offline",
        grid_params={"price_lower": 100.0, "price_upper": 112.0, "grid_num": 6},
    )
    assert req.strategy_type == "grid"
    assert req.grid_params["grid_num"] == 6


def test_backtest_request_va_valid():
    req = BacktestRequest(
        symbol="2330.TW",
        strategy_type="value_averaging",
        total_capital=100000,
        start_date="2026-04-01",
        end_date="2026-05-31",
        market_filter_enabled=False,
        llm_provider="offline",
        va_params={"total_periods": 4, "period_interval_days": 14},
    )
    assert req.va_params["total_periods"] == 4


def test_optimize_request_valid():
    req = OptimizeRequest(
        symbol="2330.TW",
        strategy_type="grid",
        total_capital=100000,
        start_date="2026-04-01",
        end_date="2026-05-31",
        max_rounds=3,
        llm_provider="offline",
        search_space={"price_lower": [90.0, 95.0], "price_upper": [110.0], "grid_num": [6]},
    )
    assert req.max_rounds == 3


def test_advisor_request_valid():
    req = AdvisorRequest(
        symbol="2330.TW",
        start_date="2026-04-01",
        end_date="2026-05-31",
        total_capital=100000,
        llm_provider="offline",
    )
    assert req.symbol == "2330.TW"
