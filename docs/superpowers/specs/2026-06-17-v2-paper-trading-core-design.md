# V2 核心設計文件 — 模擬交易引擎 + 每日摘要（Paper Trading Core）

- 日期：2026-06-17
- 來源：`PRD-Ai.md` §14（V2：AI 模擬交易版）、V1 MVP 設計文件（`2026-06-09-backtesting-copilot-mvp-design.md`）
- 範圍：V2 第一個 spec — **模擬交易引擎（Replay 重算型）+ 每日策略摘要**。**不含**通知系統、自動排程 daemon、即時 1 分 K、多標的（留待下一個 V2 spec）。

## 1. 背景與目標

V1 MVP 已完成回測 + 風控 + AI 策略建議/分析 + Streamlit 介面 + CSV/Markdown 匯出。PRD §14 的 V2「AI 模擬交易版」清單為：定時更新價格、模擬交易紀錄、每日策略摘要、風控提醒、通知系統。

本 spec 聚焦其中**可離線、確定性的核心**：

1. 一個能逐日推進的 **paper trading session**，產生模擬成交紀錄。
2. 每次推進產生**每日策略摘要**（規則式為主，LLM 為輔）。

通知與排程是「外部觸發」議題，刻意切到下一個 spec，本 spec 為它們預留掛點（CLI）。

## 2. 設計原則（延續 PRD §17 / V1）

1. 模擬成交語意必須與回測**完全一致** —— 不另寫第二套交易引擎。
2. 風控優先級高於策略與 AI；模擬交易沿用既有 `RiskEngine`，不可被繞過。
3. AI 只負責摘要與解釋；系統無金鑰時必須能完全離線運作。
4. 核心邏輯置於介面之後，不依賴 Streamlit runtime，可獨立 TDD。
5. 不破壞 V1 既有資料表與既有 `BacktestEngine` 介面。

## 3. 核心概念：Replay 重算型推進

一個 **paper session** = 一份固定的 `StrategyConfig`（symbol / 策略型別 / 參數 / `start_date` / `end_date`）+ 一個游標 `as_of`（已推進到的日期）。

「推進（advance）」流程：

```
advance(as_of):
  effective_end = min(as_of, config.end_date)
  result = BacktestEngine.run(config_with_end_date=effective_end)   # 確定性重跑
  new_trades = diff(result.trades, prev_snapshot.trades)            # 只取上次之後新增的成交
  snapshot   = 擷取最新 cash / holding_qty / equity / drawdown / 觸發風控
  status     = 依最後一根 bar 的風控結果與 (as_of >= end_date) 更新
  summary    = build_daily_summary(new_trades, new_risk_events, snapshot, prev_snapshot)
  → 持久化 snapshot + new_trades + summary
```

因為 `BacktestEngine.run()` 是純函式式、確定性的（吃 config、回傳含完整 `trades`（每筆有 `day`）的 `BacktestResult`），把 end_date 往後挪再重跑，必然是「同樣前綴 + 新 bar 新增的成交」。模擬成交與回測 100% 一致，且無需維護一套有狀態的逐 bar 引擎。

### Trade diff 定義

`new_trades` = `result.trades` 中 `day > prev_snapshot.as_of` 的成交。

正確性前提：引擎對相同 config 與相同資料前綴產生相同且**有序**的成交序列（既有引擎逐 bar append，符合此前提）。因此以 `as_of` 切點即可，無需逐筆比對欄位。若同一天有多筆成交，整批歸入該日。

### end_date 與到期

session 的策略週期由 config 的 `start_date..end_date` 固定（對應 PRD 的策略期間）。推進只能到 `min(as_of, end_date)`。當 `as_of >= end_date` → 觸發風控規則五（時間強制結算），status 轉 `EXPIRED`，摘要明示結算。

## 4. 元件設計

所有新元件置於 `src/backtesting_copilot/paper/`，皆在介面之後、可獨立單元測試。

### 4.1 `paper/session.py` — `PaperSession`（純邏輯）

- 職責：持有 config 與上一個 snapshot，呼叫**注入的** `BacktestEngine` 重跑、做 trade diff、組出 `AdvanceResult`。
- 介面：
  - `PaperSession(config, engine, prev_snapshot=None)`
  - `advance(as_of: date) -> AdvanceResult`
- `AdvanceResult` dataclass：`as_of`、`new_trades: list[Trade]`、`snapshot: PaperSnapshot`、`new_risk_events: list[str]`、`status`、`result: BacktestResult`（最新全量，供摘要與 UI 用）。
- **不碰 DB、不碰 Streamlit、不碰網路。** 資料來源透過 engine 注入的 DataProvider。

### 4.2 `paper/summary.py` — 每日摘要

- `build_daily_summary(advance_result, prev_snapshot) -> DailySummary`
- **規則式 delta 摘要（永遠可離線）**：今日新成交（買/賣/數量/金額）、權益自上次的變化、現金使用率、最大回撤、觸發的風控規則、session 狀態與原因、是否到期結算。
- **可選 LLM 自然語言版**：沿用既有 `ai/analyst.py` 的 `analyze_backtest(result, provider=...)` 注入模式，把 delta 上下文交給 `BacktestAnalyst` 產生敘述；無金鑰時自動走 OfflineProvider。LLM 為加值層，規則式輸出永遠存在。
- `DailySummary` dataclass：`as_of`、`headline`、`bullet_points: list[str]`、`status`、`narrative: str | None`。

### 4.3 `paper/store.py`（或擴充 `storage/db.py`）— 持久化

提供 session 與每日快照/摘要的 read/write helper，沿用 `storage/db.py` 既有的 `init_db` / sqlite3 `Row` 模式與可注入 `now` / id 的測試友善寫法。

## 5. 資料表（SQLite，延伸 PRD §10，不破壞既有表）

新增兩張表；模擬成交沿用既有 `trade_logs`（以 `strategy_id` 綁定 session 對應的 strategy_config）。

```sql
CREATE TABLE IF NOT EXISTS paper_sessions (
    session_id    TEXT PRIMARY KEY,
    strategy_id   TEXT NOT NULL,        -- 對應 strategy_config
    symbol        TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    params_json   TEXT NOT NULL,        -- 重建 StrategyConfig 用
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    as_of         TEXT,                 -- 目前游標；NULL = 尚未推進
    status        TEXT NOT NULL,        -- RUNNING / PAUSED_BY_MARKET / EXPIRED / CLOSED
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_snapshots (
    snapshot_id     TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    as_of           TEXT NOT NULL,
    cash            REAL NOT NULL,
    holding_qty     INTEGER NOT NULL,
    equity          REAL NOT NULL,
    cash_usage_rate REAL,
    drawdown        REAL,
    risk_events     TEXT,               -- 該次推進觸發的風控規則（; 分隔）
    summary_text    TEXT,               -- 規則式每日摘要
    narrative       TEXT,               -- 選用 LLM 敘述
    created_at      TEXT NOT NULL
);
```

每次 advance 寫入一列 `paper_snapshots`，構成游標前進的稽核軌跡（對應 PRD §9.3 可追溯性）。

`strategy_config.status` 重用既有欄位反映 session 狀態。

## 6. 推進機制

無常駐 server（沿用 V1 本機 Streamlit 定位），核心為**手動推進**：

- **Streamlit「模擬交易」分頁**：建立 session（沿用回測表單參數）、按「推進到最新資料日」或「推進一天」、檢視每日摘要、持倉與權益曲線、歷次快照。
- **CLI `python -m backtesting_copilot.paper advance --session <id>`**：執行一次推進。讓使用者日後能用作業系統排程（cron / Windows 工作排程器）掛載，為下一個 spec 的「定時更新 + 通知」預留掛點。

本 spec **不實作**內建排程 daemon 與通知；CLI 是兩者的接點。

## 7. 狀態機（對齊 PRD §5.8）

session.status 取子集：`RUNNING / PAUSED_BY_MARKET / EXPIRED / CLOSED`。

- 每次 advance 後，依最後一根 bar 的 `RiskEngine` 結果決定 `RUNNING` vs `PAUSED_BY_MARKET`。
- `as_of >= end_date` → `EXPIRED`（風控規則五，強制結算）。
- 使用者可手動 `CLOSED`（結束 session）。
- 摘要中明示目前狀態與原因。

`PAUSED_BY_ERROR`（資料/API 異常）在本 spec 視為 advance 失敗：抓取失敗時不產生新成交、不前進游標、回報錯誤，留待通知 spec 串接告警。

## 8. 資料流

```
建立 session (Streamlit 表單 / 既有回測參數)
  → 存入 paper_sessions + strategy_config
使用者按「推進」或 CLI advance
  → PaperSession.advance(as_of)
      → BacktestEngine.run(config[end=min(as_of,end_date)])  # 確定性重跑
      → diff 出 new_trades（day > 上次 as_of）
      → RiskEngine 結果 + 到期判斷 → status
  → build_daily_summary(...)（規則式；選用 LLM）
  → 持久化 snapshot + new_trades + summary
  → Streamlit 顯示每日摘要 / 持倉 / 權益曲線 / 歷史快照
```

## 9. 測試策略（TDD，沿用 V1）

- **`PaperSession.advance` diff 邏輯**（核心，pytest + fixture CSV + 注入引擎）：
  - 重跑兩次、`as_of` 各前進一天，第二次 `new_trades` 只含新 bar 的成交。
  - 無新 bar（`as_of` 未前進）時 `new_trades` 為空。
  - 跨越 `end_date` → status `EXPIRED`，且只推進到 `end_date`。
  - 觸發大盤風控的 bar → status `PAUSED_BY_MARKET`、`new_risk_events` 含對應規則。
- **`build_daily_summary`**：規則式輸出用 OfflineProvider，斷言含新成交/權益變化/狀態；不依賴網路或金鑰。
- **store round-trip**：寫入 → 讀回 session 與 snapshot，欄位一致；`now` / id 可注入以確定性測試。
- KPI 對齊 PRD §15：模擬交易語意一致性（與回測 trade 序列相同前綴）作為核心斷言。

## 10. 明確排除（留待下一個 V2 spec）

通知系統（Email / LINE / Telegram）、內建自動排程 / 定時抓價 daemon、即時 1 分 K / Tick、多標的投組、實單 API 下單。

## 11. 建置順序（後續以 implementation plan 展開）

1. `paper_sessions` / `paper_snapshots` schema + store helper（TDD round-trip）
2. `PaperSession.advance` + `AdvanceResult` + trade diff（TDD，注入引擎）
3. `build_daily_summary` 規則式（TDD，OfflineProvider）
4. LLM 敘述加值層（沿用 `analyze_backtest` 注入）
5. CLI `paper advance` 掛點
6. Streamlit「模擬交易」分頁串接
