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


# append to tests/test_optimizer.py
import json as _json


class _FakeProvider:
    """Returns a fixed JSON string as LLM output."""
    name = "fake"

    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return self._response


def test_phase2_llm_parsed():
    """Phase 2 parses valid LLM JSON and runs the suggested params."""
    suggestions = [
        {"price_lower": 92.0, "price_upper": 112.0, "grid_num": 6},
        {"price_lower": 93.0, "price_upper": 113.0, "grid_num": 8},
        {"price_lower": 91.0, "price_upper": 111.0, "grid_num": 4},
    ]
    provider = _FakeProvider(_json.dumps(suggestions))
    cfg = _make_config(
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
        max_rounds=1,
        patience=10,  # don't converge early
    )
    engine = MagicMock()
    engine.run.return_value = _make_result(total_return=0.05, mdd=-0.10, win_rate=0.6, trade_count=5)

    agent = OptimizationAgent(engine, provider)
    out = agent.run(cfg)

    # Phase1: 1 call; Phase2 round1: 3 calls => total 4
    assert engine.run.call_count == 4
    # All round-1 records present
    phase2_records = [r for r in out.all_rounds if r.round_num == 1]
    assert len(phase2_records) == 3


def test_phase2_llm_parse_fail():
    """Phase 2 handles a non-JSON LLM response gracefully."""
    provider = _FakeProvider("this is not json at all")
    cfg = _make_config(
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
        max_rounds=3,
    )
    engine = MagicMock()
    engine.run.return_value = _make_result(total_return=0.05, mdd=-0.10, win_rate=0.6, trade_count=5)

    agent = OptimizationAgent(engine, provider)
    out = agent.run(cfg)

    assert out.stopped_reason == "no_new_suggestions"
    # Only Phase 1 ran (1 combo)
    assert engine.run.call_count == 1


def test_convergence_stops():
    """stopped_reason == 'converged' when patience consecutive tests don't improve."""
    suggestions = [
        {"price_lower": 92.0, "price_upper": 112.0, "grid_num": 6},
        {"price_lower": 93.0, "price_upper": 113.0, "grid_num": 8},
        {"price_lower": 91.0, "price_upper": 111.0, "grid_num": 4},
    ]
    provider = _FakeProvider(_json.dumps(suggestions))
    cfg = _make_config(
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
        max_rounds=5,
        patience=2,
        converge_threshold=0.001,
    )
    # Always return the same score — no improvement
    engine = MagicMock()
    engine.run.return_value = _make_result(total_return=0.05, mdd=-0.10, win_rate=0.6, trade_count=5)

    agent = OptimizationAgent(engine, provider)
    out = agent.run(cfg)

    assert out.stopped_reason == "converged"


def test_max_rounds_stops():
    """stopped_reason == 'max_rounds' when score keeps improving within patience."""
    call_count = [0]
    suggestions = [
        {"price_lower": 92.0, "price_upper": 112.0, "grid_num": 6},
    ]
    provider = _FakeProvider(_json.dumps(suggestions))
    cfg = _make_config(
        search_space={"price_lower": [90.0], "price_upper": [110.0], "grid_num": [6]},
        max_rounds=3,
        patience=10,
        converge_threshold=0.001,
    )

    def always_improving(_strategy_config):
        call_count[0] += 1
        return _make_result(
            total_return=0.01 * call_count[0],
            mdd=-0.05,
            win_rate=0.5,
            trade_count=5,
        )

    engine = MagicMock()
    engine.run.side_effect = always_improving

    agent = OptimizationAgent(engine, provider)
    out = agent.run(cfg)

    assert out.stopped_reason == "max_rounds"


def test_e2e_offline(tmp_path):
    """Full Phase 1 with real engine + CSV fixture; OfflineProvider skips Phase 2."""
    import shutil
    import pathlib
    from backtesting_copilot.data.csv_provider import CsvProvider
    from backtesting_copilot.backtest.engine import BacktestEngine as RealEngine
    from backtesting_copilot.risk.engine import RiskEngine

    fixture = pathlib.Path("tests/fixtures/E2E.csv")
    csv_dir = tmp_path / "data"
    csv_dir.mkdir()
    shutil.copy(fixture, csv_dir / "E2E.csv")

    provider_data = CsvProvider(str(csv_dir))
    risk = RiskEngine()
    engine = RealEngine(provider_data, risk, market_ma_window=5)

    cfg = OptimizationConfig(
        strategy_type=StrategyType.GRID,
        symbol="E2E",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        total_capital=100_000.0,
        search_space={
            "price_lower": [95.0, 100.0],
            "price_upper": [110.0, 115.0],
            "grid_num": [4, 6],
        },
        max_rounds=0,
        top_k=3,
        market_filter_enabled=False,
    )
    agent = OptimizationAgent(engine, OfflineProvider())
    out = agent.run(cfg)

    assert out.best_params  # non-empty
    assert isinstance(out.best_score, float)
    assert len(out.all_rounds) == 8  # 2*2*2 combos
    assert out.stopped_reason == "max_rounds"
