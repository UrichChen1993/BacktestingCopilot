"""Backtest engine: bar-by-bar event loop tying strategy + risk together.

NOTE (scaffold): the per-bar fill loop is intentionally left for TDD. The
public interface is fixed here so the Streamlit app, storage, and AI layers
can be wired against it. Implement `run()` with the red-green-refactor loop
(see docs spec §5 for the daily-bar fill model and §9 for the test plan).
"""

from __future__ import annotations

from ..data.provider import DataProvider
from ..models import BacktestResult, StrategyConfig
from ..risk.engine import RiskEngine


class BacktestEngine:
    def __init__(
        self,
        data_provider: DataProvider,
        risk_engine: RiskEngine | None = None,
        *,
        market_index_symbol: str = "^TWII",
    ) -> None:
        self.data_provider = data_provider
        self.risk_engine = risk_engine or RiskEngine()
        self.market_index_symbol = market_index_symbol

    def run(self, config: StrategyConfig) -> BacktestResult:
        """Run a single-symbol, single-strategy historical backtest.

        Pending TDD implementation — see module docstring.
        """
        raise NotImplementedError(
            "BacktestEngine.run is pending TDD implementation (see docs spec §5/§9)."
        )
