"""Backtest orchestration — the tested core the Streamlit shell delegates to.

Keeps all wiring (data source, risk thresholds, engine, AI report, exports)
out of the UI so it can be unit-tested without a Streamlit runtime.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from ..ai.advisor import StrategyRecommendation, recommend_strategy
from ..ai.analyst import BacktestReport, analyze_backtest
from ..ai.optimizer import OptimizationAgent, OptimizationConfig, OptimizationResult
from ..ai.provider import LLMProvider
from ..backtest.engine import BacktestEngine
from ..config import Settings, get_settings
from ..data.csv_provider import CsvProvider
from ..data.provider import DataProvider, DataUnavailableError
from ..data.yfinance_provider import YFinanceProvider
from ..features.price_features import compute_features
from ..models import BacktestResult, StrategyConfig
from ..reports.exporters import result_to_markdown, trades_to_csv
from ..risk.engine import RiskEngine
from ..storage.db import init_db, save_backtest_run


_LOG_NAMESPACE = "backtesting_copilot"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"


def setup_logging(
    log_path: str | Path = "logs/backtest.log", *, level: int = logging.DEBUG
) -> Path:
    """Attach a file handler to the package logger; idempotent.

    Writes engine/runner logs to ``log_path`` (created if missing). Safe to call
    repeatedly — it won't stack duplicate handlers for the same file.
    """
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pkg_logger = logging.getLogger(_LOG_NAMESPACE)
    pkg_logger.setLevel(level)

    target = str(path.resolve())
    for handler in pkg_logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == target:
            return path  # already wired up

    # Roll over at local midnight so each day lands in its own file
    # (e.g. backtest.log.2026-06-15). Keep 30 days of history.
    file_handler = TimedRotatingFileHandler(
        path,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    pkg_logger.addHandler(file_handler)
    return path


@dataclass
class PipelineOutput:
    result: BacktestResult
    report: BacktestReport
    trades_csv: str
    report_md: str
    strategy_id: str | None = None


def build_provider(settings: Settings, *, csv_dir: str | Path | None = None) -> DataProvider:
    """yfinance is the online default; CSV is the offline/reproducible source."""
    if settings.default_data_source.lower() == "csv":
        return CsvProvider(csv_dir or "data")
    return YFinanceProvider()


def build_engine(settings: Settings, *, csv_dir: str | Path | None = None) -> BacktestEngine:
    provider = build_provider(settings, csv_dir=csv_dir)
    risk = RiskEngine(
        max_cash_usage_rate=settings.max_cash_usage_rate,
        max_drawdown_limit=settings.max_drawdown_limit,
    )
    return BacktestEngine(
        provider,
        risk,
        market_index_symbol=settings.market_index_symbol,
        market_ma_window=settings.market_ma_window,
    )


def run_backtest(
    config: StrategyConfig,
    engine: BacktestEngine,
    *,
    llm_provider: LLMProvider | None = None,
    db_path: str | Path | None = None,
) -> PipelineOutput:
    """Run the backtest and assemble result + AI report + export payloads.

    ``llm_provider`` defaults to the analyst's offline rule-based output.
    When ``db_path`` is given the run is persisted and its ``strategy_id`` is
    returned on the output.
    """
    setup_logging()
    result = engine.run(config)
    report = analyze_backtest(result, provider=llm_provider)
    strategy_id = None
    if db_path is not None:
        conn = init_db(db_path)
        try:
            strategy_id = save_backtest_run(conn, config, result, report)
        finally:
            conn.close()
    return PipelineOutput(
        result=result,
        report=report,
        trades_csv=trades_to_csv(result.trades),
        report_md=result_to_markdown(result),
        strategy_id=strategy_id,
    )


def suggest_strategy(
    settings: Settings,
    *,
    symbol: str,
    start: date,
    end: date,
    total_capital: float,
    csv_dir: str | Path | None = None,
    llm_provider: LLMProvider | None = None,
) -> StrategyRecommendation | None:
    """Recommend a strategy from recent price features, or ``None`` if no data.

    Fetches OHLCV for ``symbol`` over ``[start, end]`` via the configured data
    source, derives :class:`PriceFeatures`, and delegates to the rule-based
    advisor (an ``llm_provider`` adds a narrative). Returns ``None`` when the
    data source has nothing for the symbol/range.
    """
    setup_logging()
    provider = build_provider(settings, csv_dir=csv_dir)
    try:
        bars = provider.get_ohlcv(symbol, start, end)
    except DataUnavailableError:
        return None
    if not bars:
        return None
    features = compute_features(bars)
    return recommend_strategy(features, total_capital, provider=llm_provider)


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
