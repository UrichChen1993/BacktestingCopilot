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
