"""Streamlit UI — thin shell over the tested ``app.runner`` orchestration.

Run: streamlit run src/backtesting_copilot/app/streamlit_app.py

All backtest/AI/export logic lives in ``backtesting_copilot.app.runner`` (unit
tested); this module only collects inputs and renders results.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from backtesting_copilot.ai.advisor import recommend_strategy
from backtesting_copilot.ai.provider import OllamaProvider, OfflineProvider, get_provider
from backtesting_copilot.app.runner import build_engine, build_provider, run_backtest
from backtesting_copilot.config import Settings, get_settings
from backtesting_copilot.data.provider import DataUnavailableError
from backtesting_copilot.features.price_features import PriceFeatures
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
    try:
        provider = build_provider(settings, csv_dir=csv_dir)
        bars = provider.get_ohlcv(symbol, start, end)
    except Exception:
        return None
    if not bars:
        return None
    return min(b.low for b in bars), max(b.high for b in bars)


@st.cache_data(show_spinner=False)
def _fetch_bars(symbol, start, end, csv_dir):
    try:
        provider = build_provider(settings, csv_dir=csv_dir)
        return provider.get_ohlcv(symbol, start, end)
    except Exception:
        return None


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
# --- Sidebar: LLM 設定區 ---
with st.sidebar:
    st.header("LLM 設定")
    _llm_choice = st.selectbox(
        "LLM Provider",
        ["offline", "ollama", "claude", "openai", "gemini"],
        index=["offline", "ollama", "claude", "openai", "gemini"].index(
            settings.llm_provider if settings.llm_provider in ["offline", "ollama", "claude", "openai", "gemini"] else "offline"
        ),
        help="選 ollama 可指向另一台機器的 Ollama 服務"
    )
    _ollama_url = settings.ollama_base_url
    _ollama_model = settings.ollama_model
    if _llm_choice == "ollama":
        _ollama_url = st.text_input(
            "Ollama 位址",
            value=settings.ollama_base_url,
            help="另一台電腦上的 Ollama：改成 http://<IP>:11434/v1",
        )
        _ollama_model = st.text_input("Ollama 模型", value=settings.ollama_model)

    if _llm_choice != settings.llm_provider or (
        _llm_choice == "ollama" and (
            _ollama_url != settings.ollama_base_url or _ollama_model != settings.ollama_model
        )
    ):
        import os
        _overridden_settings = Settings(
            llm_provider=_llm_choice,
            anthropic_api_key=settings.anthropic_api_key,
            claude_model=settings.claude_model,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            gemini_api_key=settings.gemini_api_key,
            gemini_model=settings.gemini_model,
            ollama_base_url=_ollama_url,
            ollama_model=_ollama_model,
            default_data_source=settings.default_data_source,
            market_index_symbol=settings.market_index_symbol,
            db_path=settings.db_path,
            max_cash_usage_rate=settings.max_cash_usage_rate,
            max_drawdown_limit=settings.max_drawdown_limit,
            market_ma_window=settings.market_ma_window,
        )
        _active_provider = get_provider(_overridden_settings)
    else:
        _active_provider = get_provider(settings)

_is_offline = isinstance(_active_provider, OfflineProvider)

if _is_offline:
    st.warning(
        "⚠️ **目前為離線（規則）模式**：AI 敘述功能停用。\n\n"
        "若 Ollama 在另一台電腦，在左側「LLM 設定」選 **ollama** 並填入該機器 IP，"
        "例如 `http://192.168.1.100:11434/v1`。"
    )
else:
    _provider_label = getattr(_active_provider, "name", "?")
    _extra = f"（{_ollama_url} / {_ollama_model}）" if _llm_choice == "ollama" else ""
    st.success(f"✅ AI 已啟用：**{_provider_label}**{_extra}　|　資料來源：**{settings.default_data_source}**")

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


def _render_optimizer_tab() -> None:
    st.subheader("自動優化")
    if _is_offline:
        st.caption("Phase 1 全搜尋（規則模式）。設定 LLM API key 後可啟用 Phase 2 LLM 精細搜尋。")
    else:
        st.caption("Phase 1 全搜尋 + Phase 2 LLM 精細搜尋，自動找出最佳參數組合")

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
    opt_strategy = st.selectbox("策略（優化）", [s.value for s in StrategyType], key="opt_strategy")
    opt_symbol = st.text_input("標的（優化）", symbol, key="opt_symbol")
    opt_capital = st.number_input("總資金（優化）", min_value=1000.0, value=100_000.0, key="opt_capital")
    opt_start = st.date_input("開始日期（優化）", date(2026, 4, 1), key="opt_start")
    opt_end = st.date_input("結束日期（優化）", date(2026, 5, 31), key="opt_end")
    max_rounds = st.slider("LLM 精細輪數上限", 0, 10, 3, key="opt_max_rounds")

    if opt_strategy == StrategyType.GRID.value:
        col1, col2 = st.columns(2)
        with col1:
            pl_min = st.number_input("price_lower 最小", value=90.0, key="pl_min")
            pl_max = st.number_input("price_lower 最大", value=105.0, key="pl_max")
            pl_step = st.number_input("price_lower 步距", value=5.0, min_value=0.5, key="pl_step")
        with col2:
            pu_min = st.number_input("price_upper 最小", value=110.0, key="pu_min")
            pu_max = st.number_input("price_upper 最大", value=125.0, key="pu_max")
            pu_step = st.number_input("price_upper 步距", value=5.0, min_value=0.5, key="pu_step")
        grid_nums = st.multiselect("grid_num 候選", [4, 6, 8, 10], default=[4, 6, 8], key="opt_grid_num")

        import numpy as np
        search_space = {
            "price_lower": [round(v, 2) for v in np.arange(pl_min, pl_max + pl_step / 2, pl_step).tolist()],
            "price_upper": [round(v, 2) for v in np.arange(pu_min, pu_max + pu_step / 2, pu_step).tolist()],
            "grid_num": grid_nums or [6],
        }
        strategy_type_opt = StrategyType.GRID
    else:
        tp_vals = st.multiselect("total_periods 候選", [2, 3, 4, 6, 8], default=[3, 4, 6], key="opt_tp")
        id_vals = st.multiselect("interval_days 候選", [7, 14, 21, 30], default=[14, 21], key="opt_id")
        search_space = {
            "total_periods": tp_vals or [4],
            "interval_days": id_vals or [14],
        }
        strategy_type_opt = StrategyType.VALUE_AVERAGING

    combo_count = 1
    for v in search_space.values():
        combo_count *= len(v)
    st.caption(f"Phase 1 組合數：{combo_count}")

    if st.button("啟動優化", type="primary", key="opt_run"):
        from backtesting_copilot.ai.optimizer import OptimizationConfig
        from backtesting_copilot.app.runner import run_optimization

        opt_cfg = OptimizationConfig(
            strategy_type=strategy_type_opt,
            symbol=opt_symbol,
            start_date=opt_start,
            end_date=opt_end,
            total_capital=opt_capital,
            search_space=search_space,
            max_rounds=max_rounds,
        )
        _csv_dir = csv_dir if settings.default_data_source.lower() == "csv" else None
        engine = build_engine(settings, csv_dir=_csv_dir)
        provider = _active_provider

        progress_placeholder = st.empty()
        results_placeholder = st.empty()

        def update_progress(msg: str) -> None:
            progress_placeholder.info(msg)

        with st.spinner("優化進行中…"):
            out = run_optimization(opt_cfg, engine, provider, on_progress=update_progress)

        progress_placeholder.success(f"優化完成（{out.stopped_reason}）最佳 score = {out.best_score:.4f}")

        import pandas as _pd

        rows = []
        for r in out.all_rounds:
            row = {
                "來源": "Phase 1 全搜尋" if r.round_num == 0 else f"🤖 Phase 2 LLM 輪次 {r.round_num}",
                "score": round(r.score, 4),
                "報酬率": f"{r.result.total_return:.2%}",
                "MDD": f"{r.result.mdd:.2%}",
                "勝率": f"{r.result.win_rate:.0%}",
                "交易數": r.result.trade_count,
            }
            row.update(r.params)
            rows.append(row)

        df = _pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
        results_placeholder.dataframe(df, use_container_width=True)

        st.subheader("最佳參數")
        st.json(out.best_params)
        if st.button("套用最佳參數到回測頁", key="opt_apply"):
            for k, v in out.best_params.items():
                st.session_state[f"opt_applied_{k}"] = v
            st.info("參數已寫入 session_state，請切換到「回測」頁手動填入。")


tab_backtest, tab_optimizer = st.tabs(["回測", "自動優化"])

with tab_backtest:
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
        try:
            engine = build_engine(settings, csv_dir=csv_dir)
            out = run_backtest(
                config,
                engine,
                llm_provider=_active_provider,
                db_path=settings.db_path if persist else None,
            )
        except DataUnavailableError as exc:
            st.error(f"資料抓取失敗，未產生任何訊號：{exc}")
            st.stop()

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

        analysis_title = "AI 回測分析" if not _is_offline else "回測分析（規則模式）"
        st.subheader(analysis_title)
        if _is_offline:
            st.caption("ℹ️ 以下為規則判斷，非 LLM 生成。在左側設定 LLM Provider 後可啟用 AI 敘述。")

        col_l, col_r = st.columns([1, 2])
        with col_l:
            st.metric("風險等級", out.report.risk_level)
            st.metric("Paper Trading 就緒", "✅ 是" if out.report.paper_trading_ready else "⚠️ 尚未")
        with col_r:
            st.write(out.report.summary)
            for s in out.report.suggestions:
                st.write(f"- {s}")

        if out.report.narrative:
            st.info(f"🤖 **AI 敘述（{_active_provider.name}）**\n\n{out.report.narrative}")

        # AI 策略顧問：根據回測期間的價格特徵建議下一步策略
        if not _is_offline:
            st.subheader("🤖 AI 策略顧問")
            with st.spinner("AI 分析市場特徵中…"):
                bars = _fetch_bars(symbol, start, end, csv_dir)
            if bars and len(bars) >= 5:
                closes = [b.close for b in bars]
                highs = [b.high for b in bars]
                lows = [b.low for b in bars]
                high_40 = max(highs[-40:]) if len(highs) >= 40 else max(highs)
                low_40 = min(lows[-40:]) if len(lows) >= 40 else min(lows)
                ma_60 = sum(closes[-60:]) / len(closes[-60:]) if len(closes) >= 60 else None
                slope = None
                if ma_60 and len(closes) >= 61:
                    prev_ma = sum(closes[-61:-1]) / 60
                    slope = ma_60 - prev_ma
                features = PriceFeatures(
                    high_40=high_40,
                    low_40=low_40,
                    range_pct_40=(high_40 - low_40) / low_40 if low_40 else 0,
                    ma_60=ma_60,
                    ma_60_slope=slope,
                )
                with st.spinner("AI 生成策略建議中…"):
                    rec = recommend_strategy(features, total_capital, provider=_active_provider)
                adv_col1, adv_col2 = st.columns(2)
                adv_col1.metric("建議策略", rec.recommended_strategy.value)
                adv_col2.metric("信心度", rec.confidence_level)
                st.write("**理由：**")
                for r_item in rec.reason:
                    st.write(f"- {r_item}")
                st.write("**建議參數：**")
                st.json(rec.suggested_parameters)
                if rec.risk_notes:
                    st.write("**風險提醒：**")
                    for n in rec.risk_notes:
                        st.write(f"- ⚠️ {n}")
                if rec.narrative:
                    st.info(f"🤖 **AI 顧問說（{_active_provider.name}）**\n\n{rec.narrative}")
            else:
                st.caption("資料不足，無法產生策略建議。")

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

with tab_optimizer:
    _render_optimizer_tab()
