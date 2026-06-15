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


# append to tests/test_optimizer.py
from unittest.mock import MagicMock
from backtesting_copilot.ai.optimizer import OptimizationAgent
from backtesting_copilot.ai.provider import OfflineProvider


def test_phase1_returns_top_k():
    """Phase 1 sweeps the cartesian product and returns Top-K by score."""
    cfg = _make_config(
        search_space={"price_lower": [90.0, 95.0], "price_upper": [110.0, 115.0], "grid_num": [4, 6]},
        top_k=3,
        max_rounds=0,  # skip Phase 2
    )

    call_count = 0

    def fake_run(strategy_config):
        nonlocal call_count
        call_count += 1
        return _make_result(
            total_return=0.01 * call_count,
            mdd=-0.05,
            win_rate=0.5,
            trade_count=5,
        )

    engine = MagicMock()
    engine.run.side_effect = fake_run
    provider = OfflineProvider()

    agent = OptimizationAgent(engine, provider)
    out = agent.run(cfg)

    # cartesian: 2 * 2 * 2 = 8 combinations
    assert engine.run.call_count == 8
    assert len([r for r in out.all_rounds if r.round_num == 0]) == 8
    # best has highest score (last call = highest total_return)
    assert out.best_score > 0
    assert out.stopped_reason == "max_rounds"
