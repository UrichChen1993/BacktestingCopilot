"""Streamlit UI — thin layer over the backtesting_copilot package (PRD §13).

Run: streamlit run src/backtesting_copilot/app/streamlit_app.py

The backtest engine is still pending TDD implementation; this app already
wires inputs, validation, AI advice and the result/report views so they are
ready as the engine lands.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from backtesting_copilot.config import get_settings
from backtesting_copilot.models import (
    GridParams,
    StrategyConfig,
    StrategyType,
    ValueAveragingParams,
)
from backtesting_copilot.validator import validate_config

st.set_page_config(page_title="AI 雙軌回測 Copilot", layout="wide")
settings = get_settings()

st.title("AI 雙軌資金配置與回測決策系統")
st.caption("策略由數學規則執行 · 風控由硬規則把關 · AI 負責分析 · 使用者保留最終決策權")
st.info(f"目前 LLM provider：**{settings.llm_provider}**（無金鑰時自動離線運行）")

with st.sidebar:
    st.header("策略輸入")
    symbol = st.text_input("標的", "2330.TW")
    strategy_type = st.selectbox("策略", [s.value for s in StrategyType])
    total_capital = st.number_input("總資金", min_value=1000.0, value=100000.0, step=1000.0)
    start = st.date_input("開始日期", date(2026, 4, 1))
    end = st.date_input("結束日期", date(2026, 5, 31))

    if strategy_type == StrategyType.GRID.value:
        price_lower = st.number_input("區間下限", value=100.0)
        price_upper = st.number_input("區間上限", value=112.0)
        grid_num = st.number_input("網格層數", min_value=1, max_value=12, value=6)
    else:
        total_periods = st.number_input("總扣款次數", min_value=1, value=4)
        interval_days = st.number_input("每期間隔天數", min_value=1, value=14)

    run = st.button("驗證並回測", type="primary")

if run:
    if strategy_type == StrategyType.GRID.value:
        config = StrategyConfig(
            symbol=symbol,
            strategy_type=StrategyType.GRID,
            total_capital=total_capital,
            start_date=start,
            end_date=end,
            grid=GridParams(price_lower=price_lower, price_upper=price_upper, grid_num=int(grid_num)),
        )
    else:
        config = StrategyConfig(
            symbol=symbol,
            strategy_type=StrategyType.VALUE_AVERAGING,
            total_capital=total_capital,
            start_date=start,
            end_date=end,
            value_averaging=ValueAveragingParams(
                total_periods=int(total_periods), period_interval_days=int(interval_days)
            ),
        )

    result = validate_config(config)
    st.subheader("參數驗證")
    if result.valid:
        st.success("參數驗證通過")
    else:
        st.error("參數驗證未通過")
        for err in result.errors:
            st.write(f"- ❌ {err}")
        if result.suggested_fix:
            st.write("建議修正：", result.suggested_fix)

    st.subheader("回測")
    st.warning("回測引擎尚待 TDD 實作完成（見設計文件 §5/§9）。介面已就緒。")
