"""TDD coverage for the SQLite persistence layer (PRD §10).

Uses an in-memory database so nothing touches disk and runs are isolated.
"""

from __future__ import annotations

from datetime import date

from backtesting_copilot.ai.analyst import BacktestReport
from backtesting_copilot.models import (
    BacktestResult,
    GridParams,
    Side,
    StrategyConfig,
    StrategyType,
    Trade,
)
from backtesting_copilot.storage.db import (
    init_db,
    list_strategy_runs,
    load_ai_report,
    load_trades,
    save_backtest_run,
)


def _config() -> StrategyConfig:
    return StrategyConfig(
        symbol="2330.TW",
        strategy_type=StrategyType.GRID,
        total_capital=100000,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 5, 31),
        grid=GridParams(price_lower=100, price_upper=112, grid_num=6),
    )


def _result() -> BacktestResult:
    trades = [
        Trade(date(2026, 4, 2), Side.BUY, 100.0, 90, 9000.0, 12.8, 0.0, "grid_buy L1"),
        Trade(date(2026, 4, 9), Side.SELL, 102.0, 90, 9180.0, 13.1, 27.5, "grid_sell L1;realized=126"),
    ]
    return BacktestResult(
        strategy_type=StrategyType.GRID, symbol="2330.TW",
        start_date=date(2026, 4, 1), end_date=date(2026, 5, 31),
        initial_capital=100000, final_value=100126, total_return=0.00126, mdd=-0.02,
        realized_profit=126, unrealized_profit=0, trade_count=2, win_rate=1.0,
        cash_usage_rate=0.09, remaining_cash=91126, holding_quantity=0, avg_cost=0.0,
        market_filter_count=0, trades=trades,
    )


def _report() -> BacktestReport:
    return BacktestReport(
        summary="本次 GRID 策略回測報酬率為 0.1%…",
        risk_level="LOW",
        suggestions=["建議先進入 Paper Trading，不直接實單"],
        paper_trading_ready=True,
        narrative="（離線無 narrative）",
    )


def test_save_backtest_run_persists_config_trades_and_report():
    conn = init_db(":memory:")
    sid = save_backtest_run(
        conn, _config(), _result(), _report(),
        strategy_id="s1", now="2026-06-10T08:00:00",
    )
    assert sid == "s1"

    runs = list_strategy_runs(conn)
    assert len(runs) == 1
    assert runs[0]["strategy_id"] == "s1"
    assert runs[0]["symbol"] == "2330.TW"
    assert runs[0]["strategy_type"] == "GRID"
    assert runs[0]["created_at"] == "2026-06-10T08:00:00"

    trades = load_trades(conn, "s1")
    assert len(trades) == 2
    assert trades[0]["side"] == "BUY"
    assert trades[1]["side"] == "SELL"
    assert trades[1]["reason"].startswith("grid_sell")

    report = load_ai_report(conn, "s1")
    assert report is not None
    assert report["input_summary"].startswith("本次 GRID")
    assert report["report_type"] == "BACKTEST_ANALYSIS"


def test_save_generates_unique_ids_and_isolates_runs():
    conn = init_db(":memory:")
    a = save_backtest_run(conn, _config(), _result(), _report())
    b = save_backtest_run(conn, _config(), _result(), _report())
    assert a != b
    assert len(list_strategy_runs(conn)) == 2
    assert len(load_trades(conn, a)) == 2
    assert len(load_trades(conn, b)) == 2  # b's trades are separate from a's
