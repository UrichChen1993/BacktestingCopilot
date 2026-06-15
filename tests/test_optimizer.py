from datetime import date
from backtesting_copilot.ai.optimizer import composite_score, OptimizationConfig
from backtesting_copilot.models import BacktestResult, StrategyType


def _make_config(**kwargs) -> OptimizationConfig:
    defaults = dict(
        strategy_type=StrategyType.GRID,
        symbol="TEST",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        total_capital=100_000.0,
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
    )
    defaults.update(kwargs)
    return OptimizationConfig(**defaults)


def _make_result(**kwargs) -> BacktestResult:
    defaults = dict(
        strategy_type=StrategyType.GRID,
        symbol="TEST",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        initial_capital=100_000.0,
        final_value=105_000.0,
        total_return=0.05,
        mdd=-0.10,
        realized_profit=5_000.0,
        unrealized_profit=0.0,
        trade_count=5,
        win_rate=0.6,
        cash_usage_rate=0.8,
        remaining_cash=20_000.0,
        holding_quantity=0,
        avg_cost=0.0,
        market_filter_count=1,
    )
    defaults.update(kwargs)
    return BacktestResult(**defaults)


def test_composite_score_weights():
    cfg = _make_config()
    result = _make_result(total_return=0.10, mdd=-0.20, win_rate=0.50, trade_count=5)
    # score = 0.10*0.40 + (1-0.20)*0.35 + 0.50*0.25
    #       = 0.04 + 0.28 + 0.125 = 0.445
    score = composite_score(result, cfg)
    assert abs(score - 0.445) < 1e-9


def test_composite_score_min_trades():
    cfg = _make_config()
    result = _make_result(trade_count=2)
    assert composite_score(result, cfg) == -999
