"""Backtest analyst: turns metrics into a readable report (PRD §5.5).

Rule-based judgement (PRD §6.4) works offline; an LLM, when configured,
rewrites it into fuller prose. Judgement thresholds stay deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import BacktestResult
from .provider import LLMProvider, OfflineProvider

MDD_HIGH = -0.10  # drawdown worse than this is "high"


@dataclass
class BacktestReport:
    summary: str
    risk_level: str  # LOW | MEDIUM | HIGH
    suggestions: list[str] = field(default_factory=list)
    paper_trading_ready: bool = False
    narrative: str = ""


def analyze_backtest(
    result: BacktestResult,
    *,
    provider: LLMProvider | None = None,
) -> BacktestReport:
    provider = provider or OfflineProvider()
    suggestions: list[str] = []

    positive = result.total_return > 0
    high_mdd = result.mdd < MDD_HIGH

    if positive and not high_mdd:
        risk_level = "LOW"
        ready = True
    elif positive and high_mdd:
        risk_level = "MEDIUM"
        ready = False
        suggestions.append("降低單筆投入或重新設定區間以壓低最大回撤")
    elif not positive and result.trade_count < 5:
        risk_level = "HIGH"
        ready = False
        suggestions.append("交易次數偏少且報酬為負，標的可能不適合網格策略")
    else:
        risk_level = "MEDIUM"
        ready = False
        suggestions.append("策略效率不佳，檢視資金使用率與參數")

    if result.cash_usage_rate > 0.9 and result.total_return < 0.02:
        suggestions.append("資金使用率偏高但報酬有限，策略效率不佳")
    if result.market_filter_count > 5:
        suggestions.append("風控頻繁觸發，目前市場可能不適合短線自動策略")
    if high_mdd:
        suggestions.append("啟用大盤 60MA 風控並設定跌破 price_lower 後停止買進")
    suggestions.append("建議先進入 Paper Trading，不直接實單")

    summary = (
        f"本次 {result.strategy_type.value} 策略回測報酬率為 "
        f"{result.total_return:.1%}，最大回撤為 {result.mdd:.1%}，"
        f"交易勝率為 {result.win_rate:.0%}，交易次數 {result.trade_count} 次。"
    )

    narrative = _narrate(provider, summary, risk_level, suggestions)
    return BacktestReport(
        summary=summary,
        risk_level=risk_level,
        suggestions=suggestions,
        paper_trading_ready=ready,
        narrative=narrative,
    )


def _narrate(provider: LLMProvider, summary, risk_level, suggestions) -> str:
    if isinstance(provider, OfflineProvider):
        return ""
    prompt = (
        f"回測摘要：{summary} 風險等級：{risk_level}。建議：{suggestions}。"
        "請用繁體中文寫一段策略分析報告，包含策略總結、績效摘要、風險摘要與建議調整方向。"
        "不得保證獲利、不得宣稱能預測市場方向。"
    )
    try:
        return provider.complete(prompt)
    except Exception:  # noqa: BLE001
        return ""
