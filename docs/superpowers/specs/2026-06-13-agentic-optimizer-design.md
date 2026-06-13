# Agentic 自主優化 Agent 設計文件

**日期：** 2026-06-13  
**狀態：** 草稿（§3 以後待補）

---

## 需求摘要

使用者啟動後，agent 自主決定要跑幾輪、何時停止，過程中有進度回饋。

- **觸發方式：** 使用者在 Streamlit 啟動，agent 自主運行，有即時進度回報
- **優化目標：** 多目標平衡 — 報酬率、最大回撤、勝率同時考量
- **搜尋策略：** 兩階段 — 粗篩 grid search + LLM 精細搜尋
- **停止條件：** 混合 — 有最大輪數上限，提早收斂也可提早停

---

## §1 整體架構

```
ai/
  optimizer.py          ← 新增：OptimizationAgent + composite score
  provider.py           ← 不動，複用 LLMProvider.complete()

backtest/
  engine.py             ← 不動，被 optimizer 直接呼叫

storage/
  db.py                 ← 微擴充：加 save_optimization_run()（為跨 session 預留）

app/
  streamlit_app.py      ← 新增「自動優化」分頁，顯示進度 + 結果表格
```

### 資料流

```
使用者設定搜尋範圍
       ↓
OptimizationAgent.run()
       ↓
  [Phase 1] 粗篩 grid search
  → 每組參數呼叫 BacktestEngine
  → 計算 composite score
  → 取 Top-K（預設 K=5）
       ↓
  [Phase 2] LLM 精細搜尋（最多 max_rounds 輪）
  → 把 Top-K 結果 → LLMProvider.complete()
  → LLM 回傳建議參數列表（JSON）
  → 再回測 → 更新 best
  → 收斂判定 → 停止或繼續
       ↓
OptimizationResult（最佳參數 + 所有輪次紀錄）
       ↓
  Streamlit 顯示 + 可選擇存入 SQLite
```

### 跨 session 擴充點（預留）

`OptimizationAgent.__init__` 接受可選的 `history: list[dict]`。  
Phase 2 的 prompt 若有 history 就附上，沒有就忽略。  
DB 層未來實作 `load_optimization_history(symbol)` 填入即可，不需改核心邏輯。

---

## §2 Composite Score

```python
score = (
    total_return      * 0.40   # 報酬率（越高越好）
  + (1 + mdd)         * 0.35   # 回撤（mdd 為負值，越接近 0 越好）
  + win_rate          * 0.25   # 勝率（越高越好）
)
```

- `mdd` 為負值（例如 -0.12），所以 `1 + mdd = 0.88`，回撤越深分越低
- 若 `trade_count < 3`，強制 `score = -999`（樣本太少不可信）
- 權重透過 `OptimizationConfig` dataclass 傳入，有預設值，使用者可覆蓋

---

## §3 Phase 2 LLM 互動格式

*（待補）*

---

## §4 OptimizationAgent 介面設計

*（待補）*

---

## §5 收斂判定邏輯

*（待補）*

---

## §6 Streamlit UI 整合

*（待補）*

---

## §7 測試策略

*（待補）*
