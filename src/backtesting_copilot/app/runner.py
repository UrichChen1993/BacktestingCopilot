"""Backtest orchestration — the tested core the Streamlit shell delegates to.

Keeps all wiring (data source, risk thresholds, engine, AI report, exports)
out of the UI so it can be unit-tested without a Streamlit runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..ai.analyst import BacktestReport, analyze_backtest
from ..ai.provider import LLMProvider
from ..backtest.engine import BacktestEngine
from ..config import Settings, get_settings
from ..data.csv_provider import CsvProvider
from ..data.provider import DataProvider
from ..data.yfinance_provider import YFinanceProvider
from ..models import BacktestResult, StrategyConfig
from ..reports.exporters import result_to_markdown, trades_to_csv
from ..risk.engine import RiskEngine


@dataclass
class PipelineOutput:
    result: BacktestResult
    report: BacktestReport
    trades_csv: str
    report_md: str


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
) -> PipelineOutput:
    """Run the backtest and assemble result + AI report + export payloads.

    ``llm_provider`` defaults to the analyst's offline rule-based output.
    """
    result = engine.run(config)
    report = analyze_backtest(result, provider=llm_provider)
    return PipelineOutput(
        result=result,
        report=report,
        trades_csv=trades_to_csv(result.trades),
        report_md=result_to_markdown(result),
    )
