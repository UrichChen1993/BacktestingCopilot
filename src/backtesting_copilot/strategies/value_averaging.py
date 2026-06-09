"""Value averaging: contribution schedule and per-period order sizing (PRD §5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..models import NegativeOrderMode, ValueAveragingParams


@dataclass(frozen=True)
class VaPeriod:
    period_index: int  # 1-based
    execute_date: date
    target_value: float


def build_va_schedule(
    params: ValueAveragingParams,
    total_capital: float,
    start_date: date,
) -> list[VaPeriod]:
    """Target value at period t is ``Target_Step * t`` (PRD §5.2.3)."""
    if params.total_periods <= 0:
        raise ValueError("total_periods must be positive")
    target_step = total_capital / params.total_periods
    schedule: list[VaPeriod] = []
    for t in range(1, params.total_periods + 1):
        exec_date = start_date + timedelta(days=params.period_interval_days * (t - 1))
        schedule.append(
            VaPeriod(period_index=t, execute_date=exec_date, target_value=target_step * t)
        )
    return schedule


def order_size_for_period(
    *,
    target_value: float,
    current_value: float,
    target_step: float,
    max_order_multiplier: float,
    remaining_cash: float,
    negative_order_mode: NegativeOrderMode,
) -> float:
    """Cash amount to invest this period (PRD §5.2.3 / §5.2.4).

    Positive => buy. Negative handled per ``negative_order_mode``; for the MVP
    SKIP returns 0. Buys are capped by the single-period limit and remaining cash.
    """
    raw = target_value - current_value
    if raw <= 0:
        if negative_order_mode == NegativeOrderMode.SKIP:
            return 0.0
        # REBALANCE / TAKE_PROFIT_PARTIAL return the (negative) amount to sell;
        # the engine interprets the sign. Detailed handling is engine-side.
        return raw
    max_order = target_step * max_order_multiplier
    return min(raw, max_order, max(remaining_cash, 0.0))
