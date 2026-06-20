from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class GridParamsInput(BaseModel):
    price_lower: float
    price_upper: float
    grid_num: int


class VAParamsInput(BaseModel):
    total_periods: int
    period_interval_days: int


class BacktestRequest(BaseModel):
    symbol: str
    strategy_type: str  # "grid" | "value_averaging"
    total_capital: float
    start_date: str     # ISO date string, e.g. "2026-04-01"
    end_date: str
    market_filter_enabled: bool = True
    llm_provider: str = "offline"
    grid_params: dict[str, Any] | None = None
    va_params: dict[str, Any] | None = None


class EquityPoint(BaseModel):
    date: str
    value: float


class TradeRow(BaseModel):
    day: str
    side: str
    price: float
    quantity: float
    amount: float
    fee: float
    tax: float
    reason: str


class BacktestResponse(BaseModel):
    total_return: float
    mdd: float
    win_rate: float
    trade_count: int
    final_value: float
    realized_profit: float
    unrealized_profit: float
    market_filter_count: int
    warnings: list[str]
    equity_curve: list[EquityPoint]
    risk_level: str
    paper_trading_ready: bool
    summary: str
    suggestions: list[str]
    narrative: str
    trades: list[TradeRow]
    trades_csv: str
    report_md: str


class OptimizeRequest(BaseModel):
    symbol: str
    strategy_type: str
    total_capital: float
    start_date: str
    end_date: str
    max_rounds: int = 3
    llm_provider: str = "offline"
    search_space: dict[str, list[Any]]


class RoundResult(BaseModel):
    round_num: int
    params: dict[str, Any]
    score: float
    total_return: float
    mdd: float
    win_rate: float
    trade_count: int


class OptimizeResponse(BaseModel):
    best_params: dict[str, Any]
    best_score: float
    stopped_reason: str
    all_rounds: list[RoundResult]


class AdvisorRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    total_capital: float
    llm_provider: str = "offline"


class AdvisorResponse(BaseModel):
    recommended_strategy: str
    confidence_level: str
    reason: list[str]
    suggested_parameters: dict[str, Any]
    risk_notes: list[str]
    narrative: str
