"""Backtest analyst: turns metrics into a readable report (PRD §5.5).

Rule-based judgement (PRD §6.4) works offline; an LLM, when configured,
rewrites it into fuller prose. Judgement thresholds stay deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import BacktestResult
from .provider import LLMProvider, OfflineProvider

# 最大回撤低於 -10% 視為「高風險」
MDD_HIGH = -0.10  # drawdown worse than this is "high"


@dataclass
class BacktestReport:
    summary: str          # 一句話摘要（策略類型、報酬率、回撤、勝率）
    risk_level: str       # 風險等級：LOW | MEDIUM | HIGH
    suggestions: list[str] = field(default_factory=list)  # 人工規則產生的改善建議
    paper_trading_ready: bool = False  # 是否達到進入模擬交易的門檻
    narrative: str = ""   # 由 LLM 潤飾後的完整敘述報告（離線時為空字串）


def analyze_backtest(
    result: BacktestResult,
    *,
    provider: LLMProvider | None = None,  # 傳入 None 時自動使用 OfflineProvider（純規則）
) -> BacktestReport:
    """根據回測結果產生分析報告。

    流程：
    1. 用確定性規則判斷風險等級與是否可進入 paper trading。
    2. 依各項指標追加改善建議。
    3. 若有 LLM provider，呼叫 _narrate 將摘要潤飾成完整敘述。
    """
    # 未傳入 provider 時預設為離線模式（不呼叫 LLM）
    provider = provider or OfflineProvider()
    suggestions: list[str] = []

    # 計算兩個關鍵旗標，後續規則全以這兩個為基礎
    positive = result.total_return > 0    # 總報酬是否為正
    high_mdd = result.mdd < MDD_HIGH      # 最大回撤是否超過 10%（MDD 為負值，故用 <）

    # --- 核心風險等級判斷（4 個互斥分支）---
    if positive and not high_mdd:
        # 報酬正且回撤可接受 → 最佳狀況，可進 paper trading
        risk_level = "LOW"
        ready = True
    elif positive and high_mdd:
        # 報酬正但回撤過大 → 需要降低部位
        risk_level = "MEDIUM"
        ready = False
        suggestions.append("降低單筆投入或重新設定區間以壓低最大回撤")
    elif not positive and result.trade_count < 5:
        # 報酬負且交易次數太少 → 標的可能不適合網格
        risk_level = "HIGH"
        ready = False
        suggestions.append("交易次數偏少且報酬為負，標的可能不適合網格策略")
    else:
        # 其餘（報酬負但交易夠多）→ 參數問題
        risk_level = "MEDIUM"
        ready = False
        suggestions.append("策略效率不佳，檢視資金使用率與參數")

    # --- 追加特定指標的細項建議（可同時觸發多條）---

    # 資金使用率超過 90% 但報酬低於 2%，顯示資金未被有效運用
    if result.cash_usage_rate > 0.9 and result.total_return < 0.02:
        suggestions.append("資金使用率偏高但報酬有限，策略效率不佳")

    # 市場過濾（風控）觸發超過 5 次，表示當前市況不適合自動策略
    if result.market_filter_count > 5:
        suggestions.append("風控頻繁觸發，目前市場可能不適合短線自動策略")

    # 回撤高時建議啟用大盤趨勢過濾
    if high_mdd:
        suggestions.append("啟用大盤 60MA 風控並設定跌破 price_lower 後停止買進")

    # 無論何種情況，都建議先走 paper trading 再實單
    suggestions.append("建議先進入 Paper Trading，不直接實單")

    # --- 產生單行摘要字串 ---
    summary = (
        f"本次 {result.strategy_type.value} 策略回測報酬率為 "
        f"{result.total_return:.1%}，最大回撤為 {result.mdd:.1%}，"
        f"交易勝率為 {result.win_rate:.0%}，交易次數 {result.trade_count} 次。"
    )

    # 呼叫 LLM 將摘要潤飾為完整敘述（離線時回傳空字串）
    narrative = _narrate(provider, summary, risk_level, suggestions)

    return BacktestReport(
        summary=summary,
        risk_level=risk_level,
        suggestions=suggestions,
        paper_trading_ready=ready,
        narrative=narrative,
    )


def _narrate(provider: LLMProvider, summary, risk_level, suggestions) -> str:
    """用 LLM 將規則產生的摘要改寫成完整敘述報告。

    離線時（OfflineProvider）直接回傳空字串，不送出任何 API 請求。
    LLM 呼叫失敗時靜默吞掉例外，避免分析主流程中斷。
    """
    # OfflineProvider 代表無 LLM，直接略過
    if isinstance(provider, OfflineProvider):
        return ""

    # 組合中文 prompt，要求 LLM 遵守合規限制（不保證獲利、不預測方向）
    prompt = (
        f"回測摘要：{summary} 風險等級：{risk_level}。建議：{suggestions}。"
        "請用繁體中文寫一段策略分析報告，包含策略總結、績效摘要、風險摘要與建議調整方向。"
        "不得保證獲利、不得宣稱能預測市場方向。"
    )
    try:
        return provider.complete(prompt)
    except Exception:  # noqa: BLE001  # 任何 LLM 錯誤都不中斷主流程
        return ""
