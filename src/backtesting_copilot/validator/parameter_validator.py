"""Validate user/AI parameters before they reach the strategy engine (PRD §5.7).

Every AI suggestion and user input passes through here. On failure we return
errors plus a best-effort ``suggested_fix`` (PRD §5.7.3).
"""

from __future__ import annotations

from ..models import (
    StrategyConfig,
    StrategyType,
    ValidationResult,
)

GRID_NUM_MIN = 6
GRID_NUM_MAX = 12
PRICE_LOWER_MAX_DISTANCE = 0.20  # price_lower must be within 20% of current price
MIN_TRADE_AMOUNT = 1000.0


def validate_config(
    config: StrategyConfig,
    *,
    current_price: float | None = None,
    capital_cap: float | None = None,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    fix: dict = {}

    if config.total_capital <= 0:
        errors.append("total_capital must be positive")
    if capital_cap is not None and config.total_capital > capital_cap:
        errors.append(f"total_capital exceeds user cap {capital_cap}")
        fix["total_capital"] = capital_cap

    if config.end_date <= config.start_date:
        errors.append("end_date must be after start_date")

    if config.strategy_type == StrategyType.GRID:
        _validate_grid(config, current_price, errors, warnings, fix)
    elif config.strategy_type == StrategyType.VALUE_AVERAGING:
        _validate_value_averaging(config, errors, warnings, fix)

    return ValidationResult(valid=not errors, errors=errors, warnings=warnings, suggested_fix=fix)


def _validate_grid(config, current_price, errors, warnings, fix) -> None:
    grid = config.grid
    if grid is None:
        errors.append("grid params required for GRID strategy")
        return

    if grid.price_upper <= grid.price_lower:
        errors.append("price_upper must be greater than price_lower")

    if not (GRID_NUM_MIN <= grid.grid_num <= GRID_NUM_MAX):
        errors.append(f"grid_num={grid.grid_num} outside MVP range {GRID_NUM_MIN}-{GRID_NUM_MAX}")
        fix["grid_num"] = min(max(grid.grid_num, GRID_NUM_MIN), GRID_NUM_MAX)

    if current_price is not None and current_price > 0:
        distance = (current_price - grid.price_lower) / current_price
        if distance > PRICE_LOWER_MAX_DISTANCE:
            errors.append("price_lower more than 20% below current price, risk too high")
            fix["price_lower"] = round(current_price * (1 - PRICE_LOWER_MAX_DISTANCE), 2)

    if grid.price_upper > grid.price_lower and grid.grid_num > 0:
        unit_capital = config.total_capital / grid.grid_num
        if unit_capital < MIN_TRADE_AMOUNT:
            errors.append("unit_capital below minimum trade amount")


def _validate_value_averaging(config, errors, warnings, fix) -> None:
    va = config.value_averaging
    if va is None:
        errors.append("value_averaging params required for VALUE_AVERAGING strategy")
        return
    if va.total_periods <= 0:
        errors.append("total_periods must be positive")
    if va.period_interval_days <= 0:
        errors.append("period_interval_days must be positive")
    if va.max_order_multiplier < 1:
        warnings.append("max_order_multiplier < 1 limits buying below the target step")
