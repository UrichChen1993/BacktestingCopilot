"""Strategy modules: pure signal generators driven by math rules (PRD §5.1, §5.2)."""

from .grid import generate_grid_levels
from .value_averaging import build_va_schedule, order_size_for_period

__all__ = ["generate_grid_levels", "build_va_schedule", "order_size_for_period"]
