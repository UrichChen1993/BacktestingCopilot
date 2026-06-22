from __future__ import annotations
from datetime import date
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backtesting_copilot.ai.optimizer import OptimizationConfig
from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.api.errors import APIValidationError, classify_exception
from backtesting_copilot.app.api.schemas import OptimizeRequest, OptimizeResponse, RoundResult
from backtesting_copilot.app.runner import build_engine, run_optimization
from backtesting_copilot.config import get_settings
from backtesting_copilot.models import StrategyType

router = APIRouter()


@router.post("/optimize", response_model=OptimizeResponse)
def run_optimize_endpoint(req: OptimizeRequest):
    try:
        try:
            stype = StrategyType(req.strategy_type.upper().replace("-", "_"))
        except ValueError:
            raise APIValidationError(f"Unknown strategy_type: {req.strategy_type!r}")

        settings = get_settings()
        engine = build_engine(settings)
        provider = get_provider(settings)

        opt_cfg = OptimizationConfig(
            strategy_type=stype,
            symbol=req.symbol,
            start_date=date.fromisoformat(req.start_date),
            end_date=date.fromisoformat(req.end_date),
            total_capital=req.total_capital,
            search_space=req.search_space,
            max_rounds=req.max_rounds,
        )
        result = run_optimization(opt_cfg, engine, provider)

        return OptimizeResponse(
            best_params=result.best_params,
            best_score=result.best_score,
            stopped_reason=result.stopped_reason,
            all_rounds=[
                RoundResult(
                    round_num=r.round_num,
                    params=r.params,
                    score=r.score,
                    total_return=r.result.total_return,
                    mdd=r.result.mdd,
                    win_rate=r.result.win_rate,
                    trade_count=r.result.trade_count,
                )
                for r in result.all_rounds
            ],
        )
    except Exception as exc:
        status, body = classify_exception(exc)
        return JSONResponse(status_code=status, content=body)
