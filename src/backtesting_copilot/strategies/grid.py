"""Grid trading: node generation and per-bar trigger rules (PRD §5.1)."""

from __future__ import annotations

from ..models import GridLevel, GridParams, GridStatus


def generate_grid_levels(params: GridParams, total_capital: float) -> list[GridLevel]:
    """Build the ladder of buy/sell nodes (PRD §5.1.4).

    Level n buys at ``price_lower + (n-1)*space`` and sells one space higher.
    Quantity per level is sized later from the actual buy price at fill time;
    ``unit_capital`` is the evenly-split budget per level.
    """
    if params.grid_num <= 0:
        raise ValueError("grid_num must be positive")
    if params.price_upper <= params.price_lower:
        raise ValueError("price_upper must be greater than price_lower")

    space = params.grid_space
    unit_capital = total_capital / params.grid_num
    levels: list[GridLevel] = []
    for i in range(params.grid_num):
        buy_price = params.price_lower + i * space
        sell_price = buy_price + space
        levels.append(
            GridLevel(
                level=i + 1,
                buy_price=round(buy_price, 4),
                sell_price=round(sell_price, 4),
                unit_capital=unit_capital,
            )
        )
    return levels


def should_buy(level: GridLevel, day_low: float) -> bool:
    """Buy when the bar's low touches/crosses the node and it's waiting (PRD §5.1.5)."""
    return level.status == GridStatus.WAIT_BUY and day_low <= level.buy_price


def should_sell(level: GridLevel, day_high: float) -> bool:
    """Sell when the bar's high reaches the node's sell price while holding."""
    return level.status == GridStatus.HOLDING and day_high >= level.sell_price
