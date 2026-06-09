# AI 雙軌資金配置與回測決策系統 — V1 MVP 設計文件

- 日期：2026-06-09
- 來源：`PRD-Ai.md`（完整版 PRD）
- 範圍：V1 MVP（回測 + 風控檢查 + AI 策略建議 + AI 回測分析 + Streamlit 介面 + CSV/Markdown 匯出），**不接實單交易**。

## 1. 已確認決策

| 項目 | 決策 |
| --- | --- |
| 第一階段範圍 | V1 MVP（PRD §13.2 功能清單） |
| 歷史資料來源 | yfinance 優先，CSV 為離線備援 |
| AI 分析層 | 可切換 LLM provider（Claude / OpenAI），**無金鑰時用規則式 Offline provider**，確保系統可離線運行 |
| 架構 | 純 Python 套件 + Streamlit 薄介面（不另起 web server；FastAPI 留待 V2） |
| Python | 3.12，使用 `.venv` 虛擬環境 |

## 2. 核心設計原則（源自 PRD §17）

1. 策略由數學規則執行（strategies/）
2. 風控由硬規則把關，優先級高於 AI 與策略（risk/）
3. AI 只負責分析、建議與解釋，不可寫入正式設定、不可繞過風控與使用者確認（ai/）
4. 使用者保留最終決策權

## 3. 套件結構

```
src/backtesting_copilot/
  models.py      # 共用 dataclass 與 Enum（策略型別、網格狀態、交易、回測結果…）
  data/          # DataProvider 介面；YFinanceProvider、CsvProvider；OHLCV + 大盤指數
  features/      # 價格特徵：20/40 日高低、ATR、均線、斜率、波動度
  strategies/    # GridStrategy、ValueAveragingStrategy — 純訊號產生器
  risk/          # RiskEngine — 硬規則，回測中即時介入，覆蓋一切
  validator/     # ParameterValidator — 進引擎前擋下不合理參數並建議修正
  backtest/      # BacktestEngine（逐根 bar 事件迴圈）+ metrics（報酬、MDD、勝率…）
  ai/            # LLMProvider 抽象：ClaudeProvider / OpenAIProvider / OfflineProvider
                 #   + StrategyAdvisor、ParameterSuggester、BacktestAnalyst
  storage/       # SQLite repos（strategy_config、grid_levels、va_schedule、trade_logs、ai_reports）
  reports/       # CSV + Markdown 匯出
  app/           # Streamlit UI
tests/           # pytest 單元測試（核心引擎以 TDD 完成）
docs/            # 規格與文件
```

## 4. 資料流（V1 回測）

```
使用者輸入 (Streamlit)
  → DataProvider 抓 OHLCV + 大盤指數
  → features 計算特徵
  → (選用) AI StrategyAdvisor / ParameterSuggester 建議策略與參數
  → ParameterValidator 驗證（失敗回 suggested_fix）
  → BacktestEngine 逐 bar 執行策略，RiskEngine 即時檢查
  → metrics 計算績效
  → AI BacktestAnalyst 產生分析報告（無金鑰則規則式報告）
  → 顯示結果 + CSV/Markdown 匯出
  → 持久化到 SQLite
```

## 5. 回測引擎語意（關鍵假設）

MVP 使用 **日 K（daily OHLCV）** 回測，採以下成交模型：

- **網格策略**：以當日 `low`/`high` 近似盤中觸價。
  - 買進：當日 `low <= buy_price` 且該格狀態為 `WAIT_BUY` → 以 `buy_price` 成交。
  - 賣出：當日 `high >= sell_price` 且該格狀態為 `HOLDING` → 以 `sell_price` 成交。
  - 同一根 bar 同時觸發買與賣時，採**保守順序**：先處理買、後處理賣（避免同根 bar 內無持倉卻賣出）。此為已知的日 K 近似限制，於報告中標註。
- **價值平均策略**：依 `period_interval_days` 在扣款日以當日 `close` 計算 `Order_Size_t`，套用單期上限與剩餘現金限制；負投入預設 `SKIP`。
- **手續費/稅**：買進收 `fee_rate`，賣出收 `fee_rate + tax_rate`，計入已實現損益。
- **大盤濾網**：抓對應指數（台股 `^TWII`）計算 60MA 與斜率；觸發時暫停買進/加碼，允許賣出，狀態 `PAUSED_BY_MARKET`。

## 6. 風控規則（PRD §5.6，回測中實作）

1. 大盤跌破 60MA 且斜率向下 → 暫停買進/加碼
2. `current_price < price_lower` → 停止新增網格買進
3. `used_capital / total_capital >= 0.9` → 停止新增買進（保留 ≥10% 現金）
4. `current_drawdown <= -10%` → 暫停策略
5. `current_date >= end_date` → 強制結算並出報告
6. 資料/API 異常 → 停止下單（回測階段對應為資料缺失保護：抓取失敗不可產生訊號）

風控優先級高於 AI 與策略；AI 不可關閉或覆蓋風控。

## 7. AI 層設計

- `LLMProvider` 介面：`complete(prompt) -> str` / `complete_json(prompt, schema) -> dict`。
- 實作：`ClaudeProvider`（anthropic）、`OpenAIProvider`（openai）、`OfflineProvider`（規則式，無外部呼叫）。
- 依環境變數 `LLM_PROVIDER` 與對應金鑰選擇；金鑰缺失自動 fallback 到 Offline。
- 三個應用：`StrategyAdvisor`（建議 GRID/VALUE_AVERAGING + 信心 + 理由 + 參數 + 風險）、`ParameterSuggester`（依特徵給參數）、`BacktestAnalyst`（回測結果轉自然語言報告）。
- AI 輸出皆為「建議」，須再過 ParameterValidator 與 RiskEngine。

## 8. 資料表（SQLite，PRD §10）

`strategy_config`、`grid_levels`、`value_averaging_schedule`、`trade_logs`、`ai_reports`，欄位照 PRD §10 草案。

## 9. 測試策略

- 確定性核心（strategies、backtest、metrics、risk、validator、features、grid 節點產生）以 **TDD / pytest** 完整覆蓋。
- 資料層與 AI 層置於介面之後，用 fixture CSV 與 OfflineProvider 測試，不依賴網路或金鑰。
- KPI（PRD §15）：參數驗證覆蓋率 100%、風控阻擋覆蓋率 100% 作為測試目標。

## 10. 明確排除（非 V1）

實單 API 下單、多標的投組、全自動交易、即時 1 分 K 串流、券商帳戶串接、通知系統（Email/LINE/Telegram，留待 V2）、REST API server（留待 V2）。

## 11. 建置順序（後續以 implementation plan 展開）

1. 專案骨架 + 設定 + 核心 models（本次）
2. data 層（yfinance + csv + fixtures）
3. features
4. strategies（grid + value averaging）+ validator — TDD
5. risk engine — TDD
6. backtest engine + metrics — TDD
7. storage（SQLite）
8. ai 層（offline 先行，再接 Claude/OpenAI）
9. reports 匯出
10. Streamlit app 串接
