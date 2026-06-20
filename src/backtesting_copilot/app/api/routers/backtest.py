from __future__ import annotations
from datetime import date
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.api.errors import APIValidationError, classify_exception
from backtesting_copilot.app.api.schemas import (
    BacktestRequest, BacktestResponse, EquityPoint, TradeRow,
)
from backtesting_copilot.app.runner import build_engine, run_backtest
from backtesting_copilot.config import get_settings
from backtesting_copilot.models import (
    GridParams, StrategyConfig, StrategyType, ValueAveragingParams,
)
from backtesting_copilot.validator import validate_config

router = APIRouter()


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _build_config(req: BacktestRequest) -> StrategyConfig:
    try:
        stype = StrategyType(req.strategy_type.upper().replace("-", "_"))
    except ValueError:
        raise APIValidationError(f"Unknown strategy_type: {req.strategy_type!r}")

    common = dict(
        symbol=req.symbol,
        total_capital=req.total_capital,
        start_date=_parse_date(req.start_date),
        end_date=_parse_date(req.end_date),
        market_filter_enabled=req.market_filter_enabled,
    )
    if stype == StrategyType.GRID:
        if not req.grid_params:
            raise APIValidationError("grid_params required for grid strategy")
        gp = req.grid_params
        return StrategyConfig(
            strategy_type=stype,
            grid=GridParams(
                price_lower=gp["price_lower"],
                price_upper=gp["price_upper"],
                grid_num=int(gp["grid_num"]),
            ),
            **common,
        )
    if not req.va_params:
        raise APIValidationError("va_params required for value_averaging strategy")
    vp = req.va_params
    return StrategyConfig(
        strategy_type=stype,
        value_averaging=ValueAveragingParams(
            total_periods=int(vp["total_periods"]),
            period_interval_days=int(vp["period_interval_days"]),
        ),
        **common,
    )


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest_endpoint(req: BacktestRequest):
    try:
        config = _build_config(req)
        validation = validate_config(config)
        if not validation.valid:
            raise APIValidationError("; ".join(validation.errors))

        settings = get_settings()
        engine = build_engine(settings)
        provider = get_provider(settings)
        out = run_backtest(config, engine, llm_provider=provider)
        r = out.result

        return BacktestResponse(
            total_return=r.total_return,
            mdd=r.mdd,
            win_rate=r.win_rate,
            trade_count=r.trade_count,
            final_value=r.final_value,
            realized_profit=r.realized_profit,
            unrealized_profit=r.unrealized_profit,
            market_filter_count=r.market_filter_count,
            warnings=r.warnings,
            equity_curve=[
                EquityPoint(date=str(d), value=v) for d, v in r.equity_curve
            ],
            risk_level=out.report.risk_level,
            paper_trading_ready=out.report.paper_trading_ready,
            summary=out.report.summary,
            suggestions=out.report.suggestions,
            narrative=out.report.narrative or "",
            trades=[
                TradeRow(
                    day=str(t.day),
                    side=t.side.value,
                    price=t.price,
                    quantity=t.quantity,
                    amount=t.amount,
                    fee=t.fee,
                    tax=t.tax,
                    reason=t.reason or "",
                )
                for t in r.trades
            ],
            trades_csv=out.trades_csv,
            report_md=out.report_md,
        )
    except Exception as exc:
        status, body = classify_exception(exc)
        return JSONResponse(status_code=status, content=body)
