"""Streamlit UI — thin shell over the tested ``app.runner`` orchestration.

Run: streamlit run src/backtesting_copilot/app/streamlit_app.py

All backtest/AI/export logic lives in ``backtesting_copilot.app.runner`` (unit
tested); this module only collects inputs and renders results.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.runner import build_engine, build_provider, run_backtest
from backtesting_copilot.config import get_settings
from backtesting_copilot.data.provider import DataUnavailableError
from backtesting_copilot.models import (
    GridParams,
    StrategyConfig,
    StrategyType,
    ValueAveragingParams,
)
from backtesting_copilot.validator import validate_config

st.set_page_config(page_title="AI 雙軌回測 Copilot", layout="wide")
settings = get_settings()


@st.cache_data(show_spinner=False)
def _recent_price_range(symbol, start, end, data_source, csv_dir):
    """Fetch the symbol's high/low over the period for grid-range defaults.

    Cached so typing in other inputs doesn't refetch. Returns ``None`` when
    data can't be loaded (offline, bad symbol, empty range) so the caller can
    fall back to static defaults.
    """
    try:
        provider = build_provider(settings, csv_dir=csv_dir)
        bars = provider.get_ohlcv(symbol, start, end)
    except Exception:
        return None
    if not bars:
        return None
    return min(b.low for b in bars), max(b.high for b in bars)

st.title("AI 雙軌資金配置與回測決策系統")
st.caption("策略由數學規則執行 · 風控由硬規則把關 · AI 負責分析 · 使用者保留最終決策權")

# Resolve the provider that will *actually* run (a configured cloud provider
# with a missing key silently degrades to offline), so the badge reflects
# reality rather than the configured intent.
provider = get_provider(settings)
llm_active = provider.name != "offline"

if llm_active:
    st.success(
        f"🟢 LLM 已啟用：目前使用 **{provider.name}**，AI 將生成完整分析敘述　|　"
        f"資料來源：**{settings.default_data_source}**"
    )
else:
    st.info(
        f"⚪ 離線模式：未呼叫 LLM，AI 分析改用規則式輸出"
        f"（設定 `LLM_PROVIDER`：**{settings.llm_provider}** 與對應金鑰即可啟用）　|　"
        f"資料來源：**{settings.default_data_source}**"
    )

with st.sidebar:
    st.header("策略輸入")
    symbol = st.text_input("標的", "2330.TW")
    strategy_type = st.selectbox("策略", [s.value for s in StrategyType])
    total_capital = st.number_input("總資金", min_value=1000.0, value=100000.0, step=1000.0)
    start = st.date_input("開始日期", date(2026, 4, 1))
    end = st.date_input("結束日期", date(2026, 5, 31))

    csv_dir = None
    if settings.default_data_source.lower() == "csv":
        csv_dir = st.text_input("CSV 目錄", "data")

    if strategy_type == StrategyType.GRID.value:
        price_range = _recent_price_range(
            symbol, start, end, settings.default_data_source, csv_dir
        )
        if price_range is not None:
            lo, hi = price_range
            st.caption(f"已依 {symbol} {start}~{end} 的近期高低自動帶入區間（{lo:.2f}~{hi:.2f}）")
        else:
            lo, hi = 100.0, 112.0
            st.caption("⚠️ 無法抓取近期價格，已套用預設區間，請自行確認")
        # Key includes symbol/dates so changing them resets defaults to the
        # freshly fetched range (Streamlit otherwise keeps the edited value).
        widget_key = f"{symbol}_{start}_{end}"
        price_lower = st.number_input("區間下限", value=lo, key=f"grid_lo_{widget_key}")
        price_upper = st.number_input("區間上限", value=hi, key=f"grid_hi_{widget_key}")
        grid_num = st.number_input("網格層數", min_value=1, max_value=12, value=6)
    else:
        total_periods = st.number_input("總扣款次數", min_value=1, value=4)
        interval_days = st.number_input("每期間隔天數", min_value=1, value=14)

    market_filter = st.checkbox("啟用大盤 60MA 濾網", value=True)
    persist = st.checkbox("儲存此次回測到資料庫 (SQLite)", value=False)

    run = st.button("驗證並回測", type="primary")


def _build_config() -> StrategyConfig:
    common = dict(
        symbol=symbol,
        total_capital=total_capital,
        start_date=start,
        end_date=end,
        market_filter_enabled=market_filter,
    )
    if strategy_type == StrategyType.GRID.value:
        return StrategyConfig(
            strategy_type=StrategyType.GRID,
            grid=GridParams(price_lower=price_lower, price_upper=price_upper, grid_num=int(grid_num)),
            **common,
        )
    return StrategyConfig(
        strategy_type=StrategyType.VALUE_AVERAGING,
        value_averaging=ValueAveragingParams(
            total_periods=int(total_periods), period_interval_days=int(interval_days)
        ),
        **common,
    )


if run:
    config = _build_config()

    st.subheader("參數驗證")
    validation = validate_config(config)
    if validation.valid:
        st.success("參數驗證通過")
    else:
        st.error("參數驗證未通過")
        for err in validation.errors:
            st.write(f"- ❌ {err}")
        if validation.suggested_fix:
            st.write("建議修正：", validation.suggested_fix)
        st.stop()

    st.subheader("回測")
    spinner_msg = (
        f"AI 分析中 — 正在呼叫 {provider.name} LLM…" if llm_active else "回測計算中…"
    )
    try:
        engine = build_engine(settings, csv_dir=csv_dir)
        with st.spinner(spinner_msg):
            out = run_backtest(
                config,
                engine,
                llm_provider=provider,
                db_path=settings.db_path if persist else None,
            )
    except DataUnavailableError as exc:
        st.error(f"資料抓取失敗，未產生任何訊號：{exc}")
        st.stop()

    if out.strategy_id:
        st.caption(f"已儲存至 `{settings.db_path}`，strategy_id = `{out.strategy_id}`")

    r = out.result
    for w in r.warnings:
        st.warning(f"⚠️ {w}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總報酬率", f"{r.total_return:.2%}")
    c2.metric("最大回撤 (MDD)", f"{r.mdd:.2%}")
    c3.metric("勝率", f"{r.win_rate:.0%}")
    c4.metric("交易次數", r.trade_count)
    c1.metric("期末總資產", f"{r.final_value:,.0f}")
    c2.metric("已實現損益", f"{r.realized_profit:,.0f}")
    c3.metric("未實現損益", f"{r.unrealized_profit:,.0f}")
    c4.metric("風控觸發次數", r.market_filter_count)

    if r.equity_curve:
        st.line_chart(
            pd.DataFrame(
                {"資產淨值": [v for _, v in r.equity_curve]},
                index=[d for d, _ in r.equity_curve],
            )
        )

    st.subheader("AI 回測分析")
    if out.report.narrative:
        st.caption(f"🟢 以下敘述由 LLM（{provider.name}）即時生成")
    else:
        st.caption("⚪ 規則式輸出（未呼叫 LLM）")
    st.write(out.report.summary)
    st.write(
        f"風險等級：**{out.report.risk_level}**　·　"
        f"Paper Trading 就緒：{'✅' if out.report.paper_trading_ready else '⚠️ 尚未'}"
    )
    for s in out.report.suggestions:
        st.write(f"- {s}")
    if out.report.narrative:
        st.write(out.report.narrative)

    st.subheader("匯出")
    d1, d2 = st.columns(2)
    d1.download_button(
        "下載交易明細 CSV", out.trades_csv, file_name=f"{r.symbol}_trades.csv", mime="text/csv"
    )
    d2.download_button(
        "下載回測報告 Markdown", out.report_md, file_name=f"{r.symbol}_report.md",
        mime="text/markdown",
    )

    with st.expander("交易明細"):
        if r.trades:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "日期": t.day, "方向": t.side.value, "價格": t.price,
                            "數量": t.quantity, "金額": t.amount, "手續費": t.fee,
                            "稅": t.tax, "備註": t.reason,
                        }
                        for t in r.trades
                    ]
                )
            )
        else:
            st.write("（本次回測無成交）")
