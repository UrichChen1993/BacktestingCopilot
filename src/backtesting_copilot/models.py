"""Shared domain models: enums and dataclasses used across all modules.

These mirror the PRD data structures (§5, §8, §10) and form the typed
contract between the strategy, risk, backtest, AI, and storage layers.

學 Python 時可以先讀這個檔案：它只定義「資料長什麼樣子」，
不做計算。這種檔案通常是理解專案名詞的入口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class StrategyType(str, Enum):
    """Which of the two strategy modules a config drives.

    Enum 適合表示固定選項；繼承 str 代表它也能自然地序列化成字串。
    """

    GRID = "GRID"
    VALUE_AVERAGING = "VALUE_AVERAGING"


class StrategyStatus(str, Enum):
    """Strategy state machine (PRD §5.8)."""

    INIT = "INIT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED_BY_MARKET = "PAUSED_BY_MARKET"
    PAUSED_BY_ERROR = "PAUSED_BY_ERROR"
    PAUSED_BY_USER = "PAUSED_BY_USER"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class GridStatus(str, Enum):
    """Per-grid-level state, prevents double buy/sell (PRD §5.1.6)."""

    WAIT_BUY = "WAIT_BUY"
    HOLDING = "HOLDING"
    SOLD = "SOLD"
    DISABLED = "DISABLED"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class NegativeOrderMode(str, Enum):
    """Value-averaging behaviour when target value is already exceeded (PRD §5.2.4)."""

    SKIP = "SKIP"
    TAKE_PROFIT_PARTIAL = "TAKE_PROFIT_PARTIAL"
    REBALANCE = "REBALANCE"


@dataclass(frozen=True)
class Bar:
    """A single OHLCV bar (daily granularity for the V1 MVP)."""

    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class GridParams:
    """Inputs for the grid trading module (PRD §5.1.2)."""

    price_lower: float
    price_upper: float
    grid_num: int

    @property
    def grid_space(self) -> float:
        # @property 讓呼叫端可以寫 params.grid_space，
        # 看起來像屬性，但實際上會即時計算。
        return (self.price_upper - self.price_lower) / self.grid_num


@dataclass(frozen=True)
class ValueAveragingParams:
    """Inputs for the value averaging module (PRD §5.2.2)."""

    total_periods: int
    period_interval_days: int
    max_order_multiplier: float = 2.0
    negative_order_mode: NegativeOrderMode = NegativeOrderMode.SKIP


@dataclass(frozen=True)
class StrategyConfig:
    """A fully specified strategy ready for validation/backtest (PRD §10.1).

    dataclass 會自動產生 __init__，所以這裡只需要列欄位。
    ``grid`` 和 ``value_averaging`` 是二選一的策略參數。
    """

    symbol: str
    strategy_type: StrategyType
    total_capital: float
    start_date: date
    end_date: date
    fee_rate: float = 0.001425
    tax_rate: float = 0.003
    market_filter_enabled: bool = True
    grid: GridParams | None = None
    value_averaging: ValueAveragingParams | None = None


@dataclass
class GridLevel:
    """A single grid node and its lifecycle (PRD §5.1.7 / §10.2)."""

    level: int
    buy_price: float
    sell_price: float
    unit_capital: float
    quantity: int = 0
    status: GridStatus = GridStatus.WAIT_BUY
    realized_profit: float = 0.0


@dataclass(frozen=True)
class Trade:
    """A filled trade in the backtest ledger (PRD §10.4)."""

    day: date
    side: Side
    price: float
    quantity: int
    amount: float
    fee: float
    tax: float
    reason: str


@dataclass
class RiskCheck:
    """Result of a risk-engine evaluation at a point in time (PRD §5.6)."""

    allow_buy: bool = True
    allow_sell: bool = True
    triggered_rules: list[str] = field(default_factory=list)
    new_status: StrategyStatus | None = None


@dataclass
class ValidationResult:
    """Output of the parameter validator (PRD §5.7)."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggested_fix: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    """Aggregated backtest output metrics (PRD §6.3).

    field(default_factory=list) 避免多個物件共用同一個預設 list。
    這是 Python dataclass 很重要的小陷阱。
    """

    strategy_type: StrategyType
    symbol: str
    start_date: date
    end_date: date
    initial_capital: float
    final_value: float
    total_return: float
    mdd: float
    realized_profit: float
    unrealized_profit: float
    trade_count: int
    win_rate: float
    cash_usage_rate: float
    remaining_cash: float
    holding_quantity: int
    avg_cost: float
    market_filter_count: int
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
