"""SQLite schema and connection helper (PRD §10).

Schema only for the scaffold; repository read/write helpers are added as the
storage layer is built out.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid import cycles; only needed for type hints
    from ..ai.analyst import BacktestReport
    from ..models import BacktestResult, StrategyConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_config (
    strategy_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    total_capital REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL,
    market_filter_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grid_levels (
    grid_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    level INTEGER NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    unit_capital REAL NOT NULL,
    quantity INTEGER,
    status TEXT NOT NULL,
    buy_order_id TEXT,
    sell_order_id TEXT,
    realized_profit REAL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_averaging_schedule (
    schedule_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    period_index INTEGER NOT NULL,
    target_value REAL NOT NULL,
    current_value REAL,
    raw_order_size REAL,
    final_order_size REAL,
    status TEXT NOT NULL,
    execute_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_logs (
    trade_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    amount REAL NOT NULL,
    fee REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_reports (
    report_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    input_summary TEXT,
    ai_analysis TEXT,
    risk_notes TEXT,
    created_at TEXT NOT NULL
);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Create the database (if needed) and return an open connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def save_backtest_run(
    conn: sqlite3.Connection,
    config: "StrategyConfig",
    result: "BacktestResult",
    report: "BacktestReport",
    *,
    strategy_id: str | None = None,
    now: str | None = None,
    status: str = "EXPIRED",
) -> str:
    """Persist one backtest run (config + trades + AI report) atomically.

    Returns the ``strategy_id`` used (generated when not supplied). ``now`` and
    ``strategy_id`` are injectable for deterministic tests.
    """
    sid = strategy_id or uuid.uuid4().hex
    ts = now or datetime.now().isoformat(timespec="seconds")

    with conn:  # single transaction; rolls back on error
        conn.execute(
            """INSERT INTO strategy_config
               (strategy_id, symbol, strategy_type, total_capital, start_date,
                end_date, status, market_filter_enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sid, config.symbol, config.strategy_type.value, config.total_capital,
                config.start_date.isoformat(), config.end_date.isoformat(), status,
                int(config.market_filter_enabled), ts, ts,
            ),
        )
        conn.executemany(
            """INSERT INTO trade_logs
               (trade_id, strategy_id, symbol, side, price, quantity, amount,
                fee, tax, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    uuid.uuid4().hex, sid, result.symbol, t.side.value, t.price,
                    t.quantity, t.amount, t.fee, t.tax, t.reason, t.day.isoformat(),
                )
                for t in result.trades
            ],
        )
        conn.execute(
            """INSERT INTO ai_reports
               (report_id, strategy_id, report_type, input_summary, ai_analysis,
                risk_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                uuid.uuid4().hex, sid, "BACKTEST_ANALYSIS", report.summary,
                report.narrative, f"{report.risk_level}: " + "; ".join(report.suggestions),
                ts,
            ),
        )
    return sid


def list_strategy_runs(conn: sqlite3.Connection) -> list[dict]:
    """All persisted runs, newest first."""
    rows = conn.execute(
        "SELECT * FROM strategy_config ORDER BY created_at DESC, rowid DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def load_trades(conn: sqlite3.Connection, strategy_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM trade_logs WHERE strategy_id = ? ORDER BY created_at, rowid",
        (strategy_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_ai_report(conn: sqlite3.Connection, strategy_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM ai_reports WHERE strategy_id = ? ORDER BY created_at DESC LIMIT 1",
        (strategy_id,),
    ).fetchone()
    return dict(row) if row else None
