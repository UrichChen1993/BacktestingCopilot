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
    market_filter_enabled: bool = True


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


def _params_to_config(opt_cfg: OptimizationConfig, params: dict) -> StrategyConfig:
    """Build a StrategyConfig from optimizer config + a params dict."""
    if opt_cfg.strategy_type == StrategyType.GRID:
        return StrategyConfig(
            symbol=opt_cfg.symbol,
            strategy_type=StrategyType.GRID,
            total_capital=opt_cfg.total_capital,
            start_date=opt_cfg.start_date,
            end_date=opt_cfg.end_date,
            market_filter_enabled=opt_cfg.market_filter_enabled,
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
        market_filter_enabled=opt_cfg.market_filter_enabled,
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
