from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backtesting_copilot.ai.advisor import recommend_strategy
from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.api.errors import classify_exception
from backtesting_copilot.app.api.schemas import AdvisorResponse
from backtesting_copilot.app.runner import build_provider
from backtesting_copilot.config import get_settings
from backtesting_copilot.features.price_features import PriceFeatures, compute_features

router = APIRouter()


@router.get("/advisor", response_model=AdvisorResponse)
def get_advisor(
    symbol: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    total_capital: float = Query(...),
    llm_provider: str = Query("offline"),
    market_filter_enabled: bool = Query(False),
):
    try:
        settings = get_settings()
        data_provider = build_provider(settings)
        bars = data_provider.get_ohlcv(
            symbol,
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
        )

        if not bars or len(bars) < 2:
            features = PriceFeatures(
                last_close=0, high_20=0, low_20=0,
                high_40=0, low_40=0, range_pct_40=0,
                ma_60=None, atr_14=0, stdev_20=0,
                ma_60_slope=None, price_vs_ma60=None,
            )
        else:
            features = compute_features(bars)

        llm = get_provider(settings)
        rec = recommend_strategy(
            features,
            total_capital,
            provider=llm,
            market_filter_enabled=market_filter_enabled,
        )

        return AdvisorResponse(
            recommended_strategy=rec.recommended_strategy.value,
            confidence_level=rec.confidence_level,
            reason=rec.reason,
            suggested_parameters=rec.suggested_parameters,
            risk_notes=rec.risk_notes,
            narrative=rec.narrative or "",
        )
    except Exception as exc:
        status, body = classify_exception(exc)
        return JSONResponse(status_code=status, content=body)
