# MVP 測試指南

- 對象：V1 MVP（回測 + 風控 + AI 分析 + 匯出）
- 搭配文件：[設計文件 §5 成交語意 / §6 風控 / §9 測試策略](superpowers/specs/2026-06-09-backtesting-copilot-mvp-design.md)、`PRD-Ai.md`

本指南分三層：**(1) 自動化測試**（已可跑、CI 主力）、**(2) 端到端手動測試**（用腳本或 Streamlit 實跑一次完整回測）、**(3) 驗收清單**（對照 PRD/spec 逐項勾）。

---

## 0. 環境準備

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[ai,dev]"     # dev=pytest/cov；ai=anthropic/openai（可選）
copy .env.example .env          # 填金鑰則線上 AI；留空則規則式離線
```

> 確定性核心（strategies/risk/backtest/metrics/validator/features）**不需要任何金鑰或網路**即可測。AI 線上層與 yfinance 即時抓取才需要金鑰/連線。

---

## 1. 自動化測試（pytest）

### 1.1 全套執行

```powershell
pytest                       # 目前 20 passed
pytest -v                    # 看每個測試名稱
pytest --cov --cov-report=term-missing   # 覆蓋率 + 未覆蓋行號
```

設定在 `pyproject.toml`（`pythonpath=src`、`testpaths=tests`），從專案根目錄直接 `pytest` 即可。

### 1.2 目前覆蓋的範圍

| 檔案 | 鎖定的行為 |
| --- | --- |
| `tests/test_scaffold.py`（12） | grid 節點產生/觸發、VA 排程與單期金額、validator 擋參數、metrics 公式、features、risk 兩條規則、AI 離線建議/報告 |
| `tests/test_backtest_engine.py`（8） | 引擎事件迴圈：grid 買/賣/手續費稅、60MA 煞車擋買、VA 累積與跌價加碼、經真實 `CsvProvider` 的端到端 |

### 1.3 KPI 測試目標（PRD §15 / spec §9）

這兩項是 MVP 的硬指標，新增規則時務必補測試維持 100%：

- **參數驗證覆蓋率 100%**：`validator/parameter_validator.py` 每條 reject/warn 規則都要有對應測試（含 `suggested_fix`）。
- **風控阻擋覆蓋率 100%**：`risk/engine.py` 每條規則（60MA 煞車、跌破下限、資金使用率、最大回撤）都要有「觸發 → 擋買」測試，且在引擎層驗證 `allow_buy=False` 確實阻止成交。
  - ✅ 四條規則皆已在引擎事件迴圈層覆蓋（`tests/test_backtest_engine.py`）：60MA 煞車、跌破下限（grid）、資金使用率、最大回撤（後兩者用 VA 隔離 price-position 干擾，並以 mutation 驗證測試確實鎖住對應輸入）。

### 1.4 寫新測試的節奏（TDD）

沿用本次引擎的 red-green-refactor：先寫會失敗的測試 → 跑出預期紅燈 → 最小實作轉綠 → 重構。資料一律用 in-memory provider 或 fixture CSV，**不依賴網路**。可參考 `tests/test_backtest_engine.py` 的 `ListProvider`。

---

## 2. 端到端手動測試

### 2.1 用腳本實跑一次回測（推薦，免網路免 UI）

引擎已完成，可直接用 `CsvProvider` + 一份 OHLCV CSV 跑完整流程並匯出報告。新增 `tests/fixtures/<SYMBOL>.csv`（欄位 `date,open,high,low,close,volume`），然後：

```python
# scratch_run.py — 放專案根目錄，python scratch_run.py
from datetime import date
from pathlib import Path

from backtesting_copilot.data.csv_provider import CsvProvider
from backtesting_copilot.models import GridParams, StrategyConfig, StrategyType
from backtesting_copilot.validator import validate_config
from backtesting_copilot.backtest.engine import BacktestEngine
from backtesting_copilot.ai.analyst import analyze_backtest
from backtesting_copilot.reports.exporters import result_to_markdown, trades_to_csv

config = StrategyConfig(
    symbol="E2E",
    strategy_type=StrategyType.GRID,
    total_capital=20000,
    start_date=date(2026, 1, 1),
    end_date=date(2026, 1, 10),
    market_filter_enabled=False,                       # 無大盤指數 CSV 時關閉
    grid=GridParams(price_lower=100, price_upper=104, grid_num=2),
)

# 1) 參數驗證（進引擎前的守門）
assert validate_config(config).valid

# 2) 回測。market_ma_window 預設 60；資料不足 60 根時濾網不啟動。
provider = CsvProvider(Path("tests/fixtures"))
result = BacktestEngine(provider).run(config)
print("總報酬", result.total_return, "交易數", result.trade_count, "MDD", result.mdd)

# 3) AI 分析（無金鑰 → 規則式離線報告）
print(analyze_backtest(result).summary)

# 4) 匯出
Path("report.md").write_text(result_to_markdown(result), encoding="utf-8")
Path("trades.csv").write_text(trades_to_csv(result.trades), encoding="utf-8")
```

**檢查點**：`total_return`/`realized_profit` 數字合理、平倉後 `realized_profit ≈ final_value − initial_capital`、`report.md` 與 `trades.csv` 內容正確。

### 2.2 用真實資料（yfinance）

把 provider 換成 `YFinanceProvider`（需連線），`symbol` 用真實代碼（台股如 `2330.TW`），`market_filter_enabled=True` 並確保回測期間有足夠歷史讓 60MA 成形（建議起始日往前預留 ≥60 個交易日的資料，或縮短 `market_ma_window` 做煙霧測試）。

> ⚠️ 此為網路/外部相依測試，會因停牌、假日、資料缺漏而波動，**不要放進 CI**；當作手動冒煙測試。抓取失敗應拋 `DataUnavailableError` 而非產生訊號。

### 2.3 Streamlit 介面

```powershell
streamlit run src/backtesting_copilot/app/streamlit_app.py
```

> ⚠️ **已知限制（待修）**：目前 `app/streamlit_app.py` 只做到參數驗證，回測區塊仍顯示「引擎尚待實作」的警告，**尚未接上已完成的 `BacktestEngine`**。要做 UI 端到端測試前，需先把 app 接到引擎（呼叫 `BacktestEngine(provider).run(config)`、顯示 `BacktestResult` 與 equity curve、提供 CSV/MD 下載）。在那之前，UI 測試僅能驗證輸入與驗證流程。

### 2.4 AI 層：離線 vs 線上

- **離線（預設）**：`.env` 不填金鑰，`get_settings().llm_provider` 走規則式；`recommend_strategy` / `analyze_backtest` 必須能無金鑰產出結果（已有單元測試）。
- **線上**：填 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 並設 `LLM_PROVIDER`。手動驗證：相同輸入下線上報告能產出且不崩、金鑰錯誤/額度耗盡時**自動 fallback 回離線**而非中斷。
  - 鐵則檢查：AI 輸出只是「建議」，仍需再過 `validate_config` 與 `RiskEngine`；AI 不可繞過風控或寫入正式設定（spec §2/§7）。

---

## 3. 驗收清單（對照 PRD/spec）

回測語意（spec §5）：

- [ ] 網格買進：當日 `low <= buy_price` 且狀態 `WAIT_BUY` → 以 `buy_price` 成交
- [ ] 網格賣出：當日 `high >= sell_price` 且狀態 `HOLDING` → 以 `sell_price` 成交
- [ ] 同根 bar 同時觸發：先買後賣（保守順序）
- [ ] 價值平均：扣款日以當日 `close` 計 `Order_Size_t`，套單期上限與剩餘現金；負投入 `SKIP`
- [ ] 手續費/稅：買收 `fee_rate`、賣收 `fee_rate+tax_rate`，**皆計入已實現損益**
- [ ] 大盤濾網：跌破 60MA 且斜率向下 → 暫停買進/加碼、允許賣出，計入 `market_filter_count`

風控硬規則（spec §6，每條都要能擋）：

- [ ] 大盤 60MA 煞車 → 擋買
- [ ] `current_price < price_lower` → 停止新增網格買進
- [ ] `used/total >= 0.9` → 停止新增買進（保留 ≥10% 現金）
- [ ] `drawdown <= −10%` → 暫停策略
- [ ] 資料缺失/抓取失敗 → 不產生訊號（拋 `DataUnavailableError`）

輸出與匯出：

- [ ] `BacktestResult` 各欄位數字一致（平倉後 `realized ≈ final − initial`）
- [ ] `trades_to_csv` / `result_to_markdown` 內容正確、可開啟
- [ ] AI 報告（離線可用、線上可 fallback）

---

## 4. 已知限制（測試時心裡有數）

- **日 K 近似**：盤中觸價用 `low`/`high` 近似，無法還原當日真實成交順序；同根 bar 先買後賣是刻意的保守假設。
- **Streamlit 尚未接引擎**（見 §2.3），UI 端到端待補 —— 這是 MVP 收尾前最後一個明顯缺口。
- 回測不保證未來績效；網格單邊下跌會累積浮虧、價值平均連跌會快速消耗現金。
