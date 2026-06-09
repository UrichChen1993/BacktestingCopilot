"""SQLite schema and connection helper (PRD §10).

Schema only for the scaffold; repository read/write helpers are added as the
storage layer is built out.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
