"""TDD coverage for the app runner — the tested orchestration layer the thin
Streamlit shell delegates to (provider selection + full backtest pipeline)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backtesting_copilot.app.runner import (
    build_engine,
    build_provider,
    run_backtest,
    suggest_strategy,
)
from backtesting_copilot.config import Settings
from backtesting_copilot.data.csv_provider import CsvProvider
from backtesting_copilot.data.yfinance_provider import YFinanceProvider
from backtesting_copilot.models import GridParams, StrategyConfig, StrategyType

FIXTURES = Path(__file__).parent / "fixtures"


def _e2e_config() -> StrategyConfig:
    return StrategyConfig(
        symbol="E2E",
        strategy_type=StrategyType.GRID,
        total_capital=20000,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        fee_rate=0.0,
        tax_rate=0.0,
        market_filter_enabled=False,
        grid=GridParams(price_lower=100, price_upper=104, grid_num=2),
    )


def test_build_provider_selects_source():
    assert isinstance(build_provider(Settings(default_data_source="csv"), csv_dir=FIXTURES), CsvProvider)
    assert isinstance(build_provider(Settings(default_data_source="yfinance")), YFinanceProvider)


def test_run_backtest_produces_result_report_and_exports():
    settings = Settings(default_data_source="csv", market_index_symbol="^TWII")
    engine = build_engine(settings, csv_dir=FIXTURES)
    out = run_backtest(_e2e_config(), engine)

    # same fixture-driven grid run as the engine e2e test
    assert out.result.trade_count == 4
    assert out.result.final_value == 20396
    # report is offline-capable and non-empty
    assert out.report.summary
    assert out.report.risk_level in ("LOW", "MEDIUM", "HIGH")
    # exports are wired
    assert out.trades_csv.startswith("date,side,price")
    assert out.report_md.startswith("# 回測報告")
    # no persistence requested -> no strategy_id
    assert out.strategy_id is None


def test_suggest_strategy_returns_recommendation_from_data():
    settings = Settings(default_data_source="csv")
    rec = suggest_strategy(
        settings,
        symbol="E2E",
        start=date(2026, 1, 1),
        end=date(2026, 1, 10),
        total_capital=20000,
        csv_dir=FIXTURES,
    )
    assert rec is not None
    assert rec.recommended_strategy in (StrategyType.GRID, StrategyType.VALUE_AVERAGING)
    assert rec.confidence_level in ("LOW", "MEDIUM", "HIGH")
    assert rec.reason  # non-empty rationale
    assert rec.suggested_parameters.get("total_capital") == 20000


def test_suggest_strategy_returns_none_when_data_unavailable():
    settings = Settings(default_data_source="csv")
    rec = suggest_strategy(
        settings,
        symbol="DOES_NOT_EXIST",
        start=date(2026, 1, 1),
        end=date(2026, 1, 10),
        total_capital=20000,
        csv_dir=FIXTURES,
    )
    assert rec is None


def test_run_backtest_persists_when_db_path_given(tmp_path):
    from backtesting_copilot.storage.db import init_db, list_strategy_runs, load_trades

    settings = Settings(default_data_source="csv")
    engine = build_engine(settings, csv_dir=FIXTURES)
    db_path = tmp_path / "runs.sqlite"
    out = run_backtest(_e2e_config(), engine, db_path=db_path)

    assert out.strategy_id is not None
    conn = init_db(db_path)
    runs = list_strategy_runs(conn)
    assert len(runs) == 1
    assert runs[0]["strategy_id"] == out.strategy_id
    assert len(load_trades(conn, out.strategy_id)) == out.result.trade_count
