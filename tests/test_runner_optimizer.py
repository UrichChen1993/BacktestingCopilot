from datetime import date
from unittest.mock import MagicMock, patch
from backtesting_copilot.app.runner import run_optimization
from backtesting_copilot.ai.optimizer import OptimizationConfig, OptimizationResult, RoundRecord
from backtesting_copilot.ai.provider import OfflineProvider
from backtesting_copilot.models import StrategyType, BacktestResult


def _make_result(**kwargs):
    defaults = dict(
        strategy_type=StrategyType.GRID, symbol="TEST",
        start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        initial_capital=100_000.0, final_value=105_000.0,
        total_return=0.05, mdd=-0.10, realized_profit=5_000.0,
        unrealized_profit=0.0, trade_count=5, win_rate=0.6,
        cash_usage_rate=0.8, remaining_cash=20_000.0,
        holding_quantity=0, avg_cost=0.0, market_filter_count=1,
    )
    defaults.update(kwargs)
    return BacktestResult(**defaults)


def test_run_optimization_calls_agent_and_returns_result():
    cfg = OptimizationConfig(
        strategy_type=StrategyType.GRID,
        symbol="TEST",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        total_capital=100_000.0,
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
        max_rounds=0,
    )
    mock_result = _make_result()
    expected_out = OptimizationResult(
        best_params={"price_lower": 90.0, "price_upper": 110.0, "grid_num": 6},
        best_score=0.42,
        best_result=mock_result,
        all_rounds=[RoundRecord(round_num=0, params={}, score=0.42, result=mock_result)],
        stopped_reason="max_rounds",
    )
    engine = MagicMock()
    engine.run.return_value = mock_result
    provider = OfflineProvider()

    with patch("backtesting_copilot.app.runner.OptimizationAgent") as MockAgent:
        MockAgent.return_value.run.return_value = expected_out
        out = run_optimization(cfg, engine, provider)

    MockAgent.assert_called_once_with(engine, provider)
    MockAgent.return_value.run.assert_called_once()
    assert out is expected_out


def test_run_optimization_on_progress_forwarded():
    cfg = OptimizationConfig(
        strategy_type=StrategyType.GRID, symbol="TEST",
        start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        total_capital=100_000.0,
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
        max_rounds=0,
    )
    messages = []
    engine = MagicMock()
    provider = OfflineProvider()

    with patch("backtesting_copilot.app.runner.OptimizationAgent") as MockAgent:
        def fake_run(opt_cfg, on_progress=None):
            if on_progress:
                on_progress("hello")
            r = MagicMock()
            return OptimizationResult(
                best_params={}, best_score=0.0, best_result=r,
                all_rounds=[], stopped_reason="max_rounds"
            )
        MockAgent.return_value.run.side_effect = fake_run
        run_optimization(cfg, engine, provider, on_progress=messages.append)

    assert messages == ["hello"]
