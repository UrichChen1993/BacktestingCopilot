# Agentic Optimizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-phase (grid-search + LLM) parameter optimizer to BacktestingCopilot, exposed as a Streamlit tab.

**Architecture:** `ai/optimizer.py` owns all optimization logic (composite score, Phase 1 cartesian sweep, Phase 2 LLM loop); `app/runner.py` adds a thin `run_optimization()` wrapper; `streamlit_app.py` gains a "自動優化" tab that delegates to runner and renders results. Tests mock engine/provider to keep tests fast and deterministic.

**Tech Stack:** Python 3.11, itertools (stdlib), existing `BacktestEngine`, `LLMProvider`, `StrategyConfig`/`BacktestResult` from `models.py`.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/backtesting_copilot/ai/optimizer.py` | `OptimizationConfig`, `RoundRecord`, `OptimizationResult`, `composite_score()`, `OptimizationAgent` |
| Modify | `src/backtesting_copilot/app/runner.py` | Add `run_optimization()` |
| Modify | `src/backtesting_copilot/app/streamlit_app.py` | Add "自動優化" tab |
| Create | `tests/test_optimizer.py` | All 8 unit/integration tests |

---

## Task 1: `composite_score()` — red/green/commit

**Files:**
- Create: `src/backtesting_copilot/ai/optimizer.py`
- Create: `tests/test_optimizer.py`

- [ ] **Step 1: Write the two failing tests**

```python
# tests/test_optimizer.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_optimizer.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` (file doesn't exist yet).

- [ ] **Step 3: Create `optimizer.py` with `OptimizationConfig` and `composite_score()`**

```python
# src/backtesting_copilot/ai/optimizer.py
"""Two-phase parameter optimizer: grid search (Phase 1) + LLM refinement (Phase 2)."""

from __future__ import annotations

import itertools
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from ..backtest.engine import BacktestEngine
from ..models import (
    BacktestResult,
    GridParams,
    StrategyConfig,
    StrategyType,
    ValueAveragingParams,
)
from .provider import LLMProvider, OfflineProvider

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    strategy_type: StrategyType
    symbol: str
    start_date: date
    end_date: date
    total_capital: float
    search_space: dict  # {"price_lower": [90,95,...], "grid_num": [4,6,8]}
    top_k: int = 5
    max_rounds: int = 5
    converge_threshold: float = 0.001
    patience: int = 2
    weight_return: float = 0.40
    weight_mdd: float = 0.35
    weight_winrate: float = 0.25
    min_trades: int = 3


@dataclass
class RoundRecord:
    round_num: int   # 0 = Phase 1
    params: dict
    score: float
    result: BacktestResult


@dataclass
class OptimizationResult:
    best_params: dict
    best_score: float
    best_result: BacktestResult
    all_rounds: list[RoundRecord]
    stopped_reason: str  # "max_rounds" | "converged" | "no_new_suggestions"


def composite_score(result: BacktestResult, cfg: OptimizationConfig) -> float:
    """Compute weighted composite score; returns -999 when trade_count < min_trades."""
    if result.trade_count < cfg.min_trades:
        return -999
    return (
        result.total_return * cfg.weight_return
        + (1 + result.mdd) * cfg.weight_mdd
        + result.win_rate * cfg.weight_winrate
    )
```

- [ ] **Step 4: Run tests — expect PASS**

```
pytest tests/test_optimizer.py::test_composite_score_weights tests/test_optimizer.py::test_composite_score_min_trades -v
```

- [ ] **Step 5: Commit**

```bash
git add src/backtesting_copilot/ai/optimizer.py tests/test_optimizer.py
git commit -m "feat(optimizer): add OptimizationConfig and composite_score"
```

---

## Task 2: Phase 1 grid sweep — red/green/commit

**Files:**
- Modify: `src/backtesting_copilot/ai/optimizer.py`
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_optimizer.py
from unittest.mock import MagicMock
from backtesting_copilot.ai.optimizer import OptimizationAgent


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
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_optimizer.py::test_phase1_returns_top_k -v
```
Expected: `AttributeError: module has no attribute 'OptimizationAgent'`.

- [ ] **Step 3: Add `_params_to_config()` helper and `OptimizationAgent` with Phase 1**

Add to `optimizer.py` after the `composite_score` function:

```python
def _params_to_config(opt_cfg: OptimizationConfig, params: dict) -> StrategyConfig:
    """Build a StrategyConfig from optimizer config + a params dict."""
    if opt_cfg.strategy_type == StrategyType.GRID:
        return StrategyConfig(
            symbol=opt_cfg.symbol,
            strategy_type=StrategyType.GRID,
            total_capital=opt_cfg.total_capital,
            start_date=opt_cfg.start_date,
            end_date=opt_cfg.end_date,
            grid=GridParams(
                price_lower=float(params["price_lower"]),
                price_upper=float(params["price_upper"]),
                grid_num=int(params["grid_num"]),
            ),
        )
    # VALUE_AVERAGING
    return StrategyConfig(
        symbol=opt_cfg.symbol,
        strategy_type=StrategyType.VALUE_AVERAGING,
        total_capital=opt_cfg.total_capital,
        start_date=opt_cfg.start_date,
        end_date=opt_cfg.end_date,
        value_averaging=ValueAveragingParams(
            total_periods=int(params["total_periods"]),
            period_interval_days=int(params["interval_days"]),
        ),
    )


class OptimizationAgent:
    def __init__(
        self,
        engine: BacktestEngine,
        provider: LLMProvider,
        history: list[dict] | None = None,
    ) -> None:
        self._engine = engine
        self._provider = provider
        self._history = history or []

    def run(
        self,
        cfg: OptimizationConfig,
        on_progress: Callable[[str], None] | None = None,
    ) -> OptimizationResult:
        notify = on_progress or (lambda _: None)
        all_rounds: list[RoundRecord] = []

        # --- Phase 1: cartesian grid search ---
        keys = list(cfg.search_space.keys())
        combos = [dict(zip(keys, vals)) for vals in itertools.product(*cfg.search_space.values())]
        notify(f"Phase 1: 測試 {len(combos)} 組參數…")
        for params in combos:
            result = self._engine.run(_params_to_config(cfg, params))
            score = composite_score(result, cfg)
            all_rounds.append(RoundRecord(round_num=0, params=params, score=score, result=result))

        top_k = sorted(all_rounds, key=lambda r: r.score, reverse=True)[: cfg.top_k]
        best = top_k[0]
        notify(f"Phase 1 完成，最佳 score={best.score:.4f}")

        if cfg.max_rounds == 0:
            return OptimizationResult(
                best_params=best.params,
                best_score=best.score,
                best_result=best.result,
                all_rounds=all_rounds,
                stopped_reason="max_rounds",
            )

        # --- Phase 2: LLM refinement ---
        stopped_reason, best_score = "max_rounds", best.score
        no_improve_count = 0

        for rnd in range(1, cfg.max_rounds + 1):
            suggestions = self._ask_llm(cfg, top_k)
            if not suggestions:
                stopped_reason = "no_new_suggestions"
                break

            for params in suggestions:
                result = self._engine.run(_params_to_config(cfg, params))
                score = composite_score(result, cfg)
                all_rounds.append(RoundRecord(round_num=rnd, params=params, score=score, result=result))
                notify(f"輪次 {rnd}：score={score:.4f} params={params}")

                if score > best_score + cfg.converge_threshold:
                    best_score = score
                    best = RoundRecord(round_num=rnd, params=params, score=score, result=result)
                    no_improve_count = 0
                else:
                    no_improve_count += 1

                if no_improve_count >= cfg.patience:
                    stopped_reason = "converged"
                    break

            if stopped_reason != "max_rounds":
                break

            top_k = sorted(all_rounds, key=lambda r: r.score, reverse=True)[: cfg.top_k]

        notify(f"優化結束（{stopped_reason}），最佳 score={best_score:.4f}")
        return OptimizationResult(
            best_params=best.params,
            best_score=best_score,
            best_result=best.result,
            all_rounds=all_rounds,
            stopped_reason=stopped_reason,
        )

    # ------------------------------------------------------------------

    def _ask_llm(self, cfg: OptimizationConfig, top_k: list[RoundRecord]) -> list[dict]:
        if isinstance(self._provider, OfflineProvider):
            return []

        top_k_data = [
            {"params": r.params, "score": round(r.score, 6),
             "total_return": round(r.result.total_return, 4),
             "mdd": round(r.result.mdd, 4),
             "win_rate": round(r.result.win_rate, 4)}
            for r in top_k
        ]
        history_data = self._history if self._history else []
        prompt = (
            f"## 搜尋範圍\n{json.dumps(cfg.search_space, ensure_ascii=False)}\n\n"
            f"## 已測試 Top-K 結果（依 composite score 降序）\n"
            f"{json.dumps(top_k_data, ensure_ascii=False)}\n\n"
            f"## 歷史輪次摘要\n{json.dumps(history_data, ensure_ascii=False)}\n\n"
            "## 任務\n"
            "根據上述結果，建議 3 組新參數組合（需在搜尋範圍內，且與已測試組合有明顯差異）。\n"
            "嚴格輸出 JSON 陣列，不得附加任何說明或 markdown。"
        )
        system = (
            "你是量化策略優化 AI，專責建議網格/價值平均策略的參數組合。"
            "只輸出 JSON 陣列，不得附加任何說明或 markdown。"
        )
        try:
            raw = self._provider.complete(prompt, system=system)
            suggestions = json.loads(raw)
            if not isinstance(suggestions, list):
                raise ValueError("expected list")
            return suggestions
        except Exception as exc:
            logger.warning("LLM suggestion parse failed: %s", exc)
            return []
```

- [ ] **Step 4: Run test — expect PASS**

```
pytest tests/test_optimizer.py::test_phase1_returns_top_k -v
```

- [ ] **Step 5: Run full suite to confirm no regressions**

```
pytest tests/ -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add src/backtesting_copilot/ai/optimizer.py tests/test_optimizer.py
git commit -m "feat(optimizer): add OptimizationAgent Phase 1 grid sweep"
```

---

## Task 3: Phase 2 LLM tests — red/green/commit

**Files:**
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write three failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_optimizer.py::test_phase2_llm_parsed tests/test_optimizer.py::test_phase2_llm_parse_fail tests/test_optimizer.py::test_convergence_stops tests/test_optimizer.py::test_max_rounds_stops -v
```
Expected: FAIL (agent exists but Phase 2 behaviour needs verification).

- [ ] **Step 3: Run tests — all should PASS with current implementation**

If any fail, inspect the `stopped_reason` logic in `OptimizationAgent.run()`. The `no_improve_count` resets inside the outer loop at start of each round. Verify the inner `break` exits the suggestions loop and the outer `if stopped_reason != "max_rounds": break` exits the rounds loop.

- [ ] **Step 4: Commit**

```bash
git add tests/test_optimizer.py
git commit -m "test(optimizer): add Phase 2 LLM, convergence, max_rounds tests"
```

---

## Task 4: End-to-end offline test — red/green/commit

**Files:**
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_optimizer.py
from backtesting_copilot.data.csv_provider import CsvProvider
from backtesting_copilot.backtest.engine import BacktestEngine as RealEngine
from backtesting_copilot.risk.engine import RiskEngine


def test_e2e_offline(tmp_path):
    """Full Phase 1 with real engine + CSV fixture; OfflineProvider skips Phase 2."""
    import shutil, pathlib
    fixture = pathlib.Path("tests/fixtures/E2E.csv")
    csv_dir = tmp_path / "data"
    csv_dir.mkdir()
    # CsvProvider expects <dir>/<SYMBOL>.csv
    shutil.copy(fixture, csv_dir / "E2E.csv")

    provider_data = CsvProvider(str(csv_dir))
    risk = RiskEngine()
    engine = RealEngine(provider_data, risk, market_ma_window=5)

    cfg = OptimizationConfig(
        strategy_type=StrategyType.GRID,
        symbol="E2E",
        start_date=date(2024, 1, 2),
        end_date=date(2024, 3, 29),
        total_capital=100_000.0,
        search_space={
            "price_lower": [95.0, 100.0],
            "price_upper": [110.0, 115.0],
            "grid_num": [4, 6],
        },
        max_rounds=0,  # Phase 1 only (OfflineProvider would skip Phase 2 anyway)
        top_k=3,
    )
    agent = OptimizationAgent(engine, OfflineProvider())
    out = agent.run(cfg)

    assert out.best_params  # non-empty
    assert isinstance(out.best_score, float)
    assert len(out.all_rounds) == 8  # 2*2*2 combos
    assert out.stopped_reason == "max_rounds"
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_optimizer.py::test_e2e_offline -v
```
Expected: FAIL or PASS — if the E2E.csv fixture exists and the real engine is wired, this may PASS immediately.

- [ ] **Step 3: Run all optimizer tests**

```
pytest tests/test_optimizer.py -v
```
All 8 tests should be green.

- [ ] **Step 4: Run full suite**

```
pytest tests/ -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_optimizer.py
git commit -m "test(optimizer): add e2e offline integration test"
```

---

## Task 5: `runner.run_optimization()` — red/green/commit

**Files:**
- Modify: `src/backtesting_copilot/app/runner.py`
- Create new test file: `tests/test_runner_optimizer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner_optimizer.py
import json
from datetime import date
from unittest.mock import MagicMock, patch
from backtesting_copilot.app.runner import run_optimization
from backtesting_copilot.ai.optimizer import OptimizationConfig, OptimizationResult, RoundRecord
from backtesting_copilot.ai.provider import OfflineProvider
from backtesting_copilot.models import StrategyType, BacktestResult


def _make_result(**kwargs):
    defaults = dict(
        strategy_type=StrategyType.GRID, symbol="TEST",
        start_date=date(2026,1,1), end_date=date(2026,3,31),
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
        start_date=date(2026,1,1), end_date=date(2026,3,31),
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
            from backtesting_copilot.ai.optimizer import OptimizationResult, RoundRecord
            r = engine.run.return_value
            return OptimizationResult(
                best_params={}, best_score=0.0, best_result=r,
                all_rounds=[], stopped_reason="max_rounds"
            )
        engine.run.return_value = MagicMock()
        MockAgent.return_value.run.side_effect = fake_run
        run_optimization(cfg, engine, provider, on_progress=messages.append)

    assert messages == ["hello"]
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_runner_optimizer.py -v
```
Expected: `ImportError: cannot import name 'run_optimization'`.

- [ ] **Step 3: Add `run_optimization()` to `runner.py`**

Add this import at the top of `runner.py`, after existing imports:

```python
from ..ai.optimizer import OptimizationAgent, OptimizationConfig, OptimizationResult
```

Add this function at the bottom of `runner.py`:

```python
def run_optimization(
    config: OptimizationConfig,
    engine: BacktestEngine,
    provider: LLMProvider,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> OptimizationResult:
    """Orchestrate OptimizationAgent; thin wrapper kept consistent with run_backtest."""
    setup_logging()
    agent = OptimizationAgent(engine, provider)
    return agent.run(config, on_progress=on_progress)
```

Also add `Callable` to the imports at the top:

```python
from collections.abc import Callable
```

- [ ] **Step 4: Run tests — expect PASS**

```
pytest tests/test_runner_optimizer.py -v
```

- [ ] **Step 5: Run full suite**

```
pytest tests/ -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add src/backtesting_copilot/app/runner.py tests/test_runner_optimizer.py
git commit -m "feat(optimizer): add runner.run_optimization() wrapper"
```

---

## Task 6: Streamlit "自動優化" tab — commit only (UI not unit-tested)

**Files:**
- Modify: `src/backtesting_copilot/app/streamlit_app.py`

- [ ] **Step 1: Wrap existing content in a "回測" tab and add "自動優化" tab**

Replace the top-level structure of `streamlit_app.py`. The sidebar stays as-is. After the `run` button definition and before the `if run:` block, insert `st.tabs()`:

```python
# Replace:
#   if run:
#       ...
# With:

tab_backtest, tab_optimizer = st.tabs(["回測", "自動優化"])

with tab_backtest:
    if run:
        # (move ALL existing `if run:` body here, indented one level)
        config = _build_config()
        ...  # existing body unchanged

with tab_optimizer:
    _render_optimizer_tab()
```

- [ ] **Step 2: Add `_render_optimizer_tab()` function** (add before `tab_backtest, tab_optimizer = ...`)

```python
def _render_optimizer_tab() -> None:
    st.subheader("自動優化")
    st.caption("Phase 1 全搜尋 + Phase 2 LLM 精細搜尋，自動找出最佳參數組合")

    opt_strategy = st.selectbox("策略（優化）", [s.value for s in StrategyType], key="opt_strategy")
    opt_symbol = st.text_input("標的（優化）", symbol, key="opt_symbol")
    opt_capital = st.number_input("總資金（優化）", min_value=1000.0, value=100_000.0, key="opt_capital")
    opt_start = st.date_input("開始日期（優化）", date(2026, 4, 1), key="opt_start")
    opt_end = st.date_input("結束日期（優化）", date(2026, 5, 31), key="opt_end")
    max_rounds = st.slider("LLM 精細輪數上限", 0, 10, 3, key="opt_max_rounds")

    if opt_strategy == StrategyType.GRID.value:
        col1, col2 = st.columns(2)
        with col1:
            pl_min = st.number_input("price_lower 最小", value=90.0, key="pl_min")
            pl_max = st.number_input("price_lower 最大", value=105.0, key="pl_max")
            pl_step = st.number_input("price_lower 步距", value=5.0, min_value=0.5, key="pl_step")
        with col2:
            pu_min = st.number_input("price_upper 最小", value=110.0, key="pu_min")
            pu_max = st.number_input("price_upper 最大", value=125.0, key="pu_max")
            pu_step = st.number_input("price_upper 步距", value=5.0, min_value=0.5, key="pu_step")
        grid_nums = st.multiselect("grid_num 候選", [4, 6, 8, 10], default=[4, 6, 8], key="opt_grid_num")

        import numpy as np
        search_space = {
            "price_lower": [round(v, 2) for v in np.arange(pl_min, pl_max + pl_step / 2, pl_step).tolist()],
            "price_upper": [round(v, 2) for v in np.arange(pu_min, pu_max + pu_step / 2, pu_step).tolist()],
            "grid_num": grid_nums or [6],
        }
        strategy_type_opt = StrategyType.GRID
    else:
        tp_vals = st.multiselect("total_periods 候選", [2, 3, 4, 6, 8], default=[3, 4, 6], key="opt_tp")
        id_vals = st.multiselect("interval_days 候選", [7, 14, 21, 30], default=[14, 21], key="opt_id")
        search_space = {
            "total_periods": tp_vals or [4],
            "interval_days": id_vals or [14],
        }
        strategy_type_opt = StrategyType.VALUE_AVERAGING

    combo_count = 1
    for v in search_space.values():
        combo_count *= len(v)
    st.caption(f"Phase 1 組合數：{combo_count}")

    if st.button("啟動優化", type="primary", key="opt_run"):
        from backtesting_copilot.ai.optimizer import OptimizationConfig
        from backtesting_copilot.app.runner import run_optimization

        opt_cfg = OptimizationConfig(
            strategy_type=strategy_type_opt,
            symbol=opt_symbol,
            start_date=opt_start,
            end_date=opt_end,
            total_capital=opt_capital,
            search_space=search_space,
            max_rounds=max_rounds,
        )
        engine = build_engine(settings, csv_dir=csv_dir if settings.default_data_source.lower() == "csv" else None)
        provider = get_provider(settings)

        progress_placeholder = st.empty()
        results_placeholder = st.empty()

        def update_progress(msg: str) -> None:
            progress_placeholder.info(msg)

        with st.spinner("優化進行中…"):
            out = run_optimization(opt_cfg, engine, provider, on_progress=update_progress)

        progress_placeholder.success(f"優化完成（{out.stopped_reason}）最佳 score = {out.best_score:.4f}")

        import pandas as pd as _pd

        rows = []
        for r in out.all_rounds:
            row = {"輪次": r.round_num, "score": round(r.score, 4),
                   "報酬率": f"{r.result.total_return:.2%}",
                   "MDD": f"{r.result.mdd:.2%}",
                   "勝率": f"{r.result.win_rate:.0%}",
                   "交易數": r.result.trade_count}
            row.update(r.params)
            rows.append(row)

        df = _pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
        results_placeholder.dataframe(df, use_container_width=True)

        st.subheader("最佳參數")
        st.json(out.best_params)
        if st.button("套用最佳參數到回測頁", key="opt_apply"):
            for k, v in out.best_params.items():
                st.session_state[f"opt_applied_{k}"] = v
            st.info("參數已寫入 session_state，請切換到「回測」頁手動填入。")
```

- [ ] **Step 2: Fix the `import pandas as pd as _pd` typo**

That line should be:

```python
import pandas as _pd
```

- [ ] **Step 3: Verify syntax**

```
python -m py_compile src/backtesting_copilot/app/streamlit_app.py && echo OK
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/backtesting_copilot/app/streamlit_app.py
git commit -m "feat(optimizer): add 自動優化 tab to Streamlit UI"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run full test suite**

```
pytest tests/ -v --tb=short
```
Expected: all tests pass (existing 31+ plus 10 new optimizer/runner tests).

- [ ] **Step 2: Syntax-check streamlit app**

```
python -m py_compile src/backtesting_copilot/app/streamlit_app.py && echo OK
```

- [ ] **Step 3: Confirm optimizer module importable**

```
python -c "from backtesting_copilot.ai.optimizer import OptimizationAgent, composite_score; print('OK')"
```

- [ ] **Step 4: Commit summary**

```bash
git log --oneline -6
```
Expected: 5-6 commits for this feature (Tasks 1–6).
