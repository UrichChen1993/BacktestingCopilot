"""Strategy advisor + parameter suggester (PRD §5.3, §5.4).

Rule-based core (works offline); an LLM provider, when present, adds a
natural-language rationale. The structured recommendation itself is always
deterministic so it is testable and never depends on a live API.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..features.price_features import PriceFeatures
from ..models import StrategyType
from .provider import LLMProvider, OfflineProvider

# Heuristic thresholds for choosing between range-bound (grid) and trending.
RANGE_BOUND_MAX_SLOPE_PCT = 0.03  # |60MA slope| small => range-bound
MIN_RANGE_PCT_FOR_GRID = 0.06  # need enough amplitude to justify grid


@dataclass
class StrategyRecommendation:
    recommended_strategy: StrategyType
    confidence_level: str  # LOW | MEDIUM | HIGH
    reason: list[str] = field(default_factory=list)
    suggested_parameters: dict = field(default_factory=dict)
    risk_notes: list[str] = field(default_factory=list)
    narrative: str = ""


def _grid_confidence(regime_p: float | None) -> str:
    if regime_p is None:
        return "MEDIUM"
    if regime_p >= 0.7:
        return "HIGH"
    if regime_p >= 0.5:
        return "MEDIUM"
    return "LOW"


def recommend_strategy(
    features: PriceFeatures,
    total_capital: float,
    *,
    provider: LLMProvider | None = None,
    market_below_ma: bool = False,
    classifier=None,  # ml.classifier.RegimeClassifier | None
    bars=None,        # list[Bar] | None, required when classifier is given
) -> StrategyRecommendation:
    provider = provider or OfflineProvider()
    reasons: list[str] = []
    risk_notes: list[str] = []

    slope_pct = None
    if features.ma_60 and features.ma_60_slope is not None and features.ma_60:
        slope_pct = features.ma_60_slope / features.ma_60

    range_ok = features.range_pct_40 >= MIN_RANGE_PCT_FOR_GRID

    regime_p = None
    if classifier is not None and bars:
        regime_p = classifier.predict_proba(bars)
        grid_suitable = regime_p >= 0.5
    else:
        grid_suitable = slope_pct is None or abs(slope_pct) <= RANGE_BOUND_MAX_SLOPE_PCT

    if range_ok and grid_suitable:
        strategy = StrategyType.GRID
        confidence = _grid_confidence(regime_p)
        if regime_p is not None:
            reasons.append(f"RNN 判定為區間盤（信心 {regime_p:.2f}）")
        else:
            reasons.append("近 40 日價格呈現區間震盪")
        reasons.append("波動率足以支撐網格交易")
        suggested = {
            "price_lower": round(features.low_40, 2),
            "price_upper": round(features.high_40, 2),
            "grid_num": 6 if features.range_pct_40 < 0.12 else 8,
            "total_capital": total_capital,
        }
        risk_notes.append("若跌破區間下緣，應暫停加碼")
        risk_notes.append("建議啟用 60MA 大盤濾網")
    else:
        strategy = StrategyType.VALUE_AVERAGING
        confidence = "MEDIUM" if not range_ok else "LOW"
        if regime_p is not None:
            reasons.append(f"RNN 判定偏趨勢盤（區間信心 {regime_p:.2f}），較適合分批布局")
        else:
            reasons.append("趨勢性較明顯或區間振幅不足，較適合分批布局")
        suggested = {
            "total_periods": 4,
            "period_interval_days": 14,
            "max_order_multiplier": 2,
            "negative_order_mode": "SKIP",
            "total_capital": total_capital,
        }
        risk_notes.append("連續下跌時價值平均可能快速消耗資金，保留單期上限")

    if market_below_ma:
        risk_notes.append("目前大盤位於 60MA 之下，買進訊號需更謹慎")

    narrative = _narrate(provider, strategy, reasons, risk_notes)
    return StrategyRecommendation(
        recommended_strategy=strategy,
        confidence_level=confidence,
        reason=reasons,
        suggested_parameters=suggested,
        risk_notes=risk_notes,
        narrative=narrative,
    )


def _narrate(provider: LLMProvider, strategy, reasons, risk_notes) -> str:
    if isinstance(provider, OfflineProvider):
        return ""  # rule-based output already carries the reasons
    prompt = (
        f"建議策略：{strategy.value}。理由：{reasons}。風險提醒：{risk_notes}。"
        "請用 3-4 句繁體中文向一般投資人解釋，不得保證獲利、不得宣稱能預測方向。"
    )
    try:
        return provider.complete(prompt)
    except Exception:  # noqa: BLE001
        return ""
