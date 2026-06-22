# Agentic 自主優化 Agent 設計文件

**日期：** 2026-06-13  
**狀態：** 完稿

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
  runner.py             ← 新增 run_optimization() 包裝
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

**System prompt（固定）：**
```
你是量化策略優化 AI，專責建議網格/價值平均策略的參數組合。
只輸出 JSON 陣列，不得附加任何說明或 markdown。
```

**User prompt template：**
```
## 搜尋範圍
{search_space_json}

## 已測試 Top-K 結果（依 composite score 降序）
{top_k_json}

## 歷史輪次摘要（若有）
{history_json}

## 任務
根據上述結果，建議 3 組新參數組合（需在搜尋範圍內，且與已測試組合有明顯差異）。
嚴格輸出 JSON 陣列，例如：
[{"price_lower": 95.0, "price_upper": 115.0, "grid_num": 8}, ...]
```

**回應解析：**
- 成功：`json.loads()` → `list[dict]`，每個 dict 做數值 clamp 到搜尋範圍邊界
- 失敗（非 JSON / schema 不符）：log warning，該輪視為「無新建議」，觸發收斂判定

---

## §4 OptimizationAgent 介面設計

```python
@dataclass
class OptimizationConfig:
    strategy_type: StrategyType
    symbol: str
    start_date: date
    end_date: date
    total_capital: float
    search_space: dict          # {"price_lower": [90,95,100,...], "grid_num": [4,6,8]}
    top_k: int = 5
    max_rounds: int = 5
    converge_threshold: float = 0.001  # score 進步小於此值算「無改善」
    patience: int = 2                   # 連續無改善幾次測試就停止
    weight_return: float = 0.40
    weight_mdd: float = 0.35
    weight_winrate: float = 0.25
    min_trades: int = 3

@dataclass
class RoundRecord:
    round_num: int      # 0 = Phase 1
    params: dict
    score: float
    result: BacktestResult

@dataclass
class OptimizationResult:
    best_params: dict
    best_score: float
    best_result: BacktestResult
    all_rounds: list[RoundRecord]
    stopped_reason: str  # "max_rounds" | "converged" | "no_new_suggestions"

class OptimizationAgent:
    def __init__(
        self,
        engine: BacktestEngine,
        provider: LLMProvider,
        history: list[dict] | None = None,
    ) -> None: ...

    def run(
        self,
        config: OptimizationConfig,
        on_progress: Callable[[str], None] | None = None,
    ) -> OptimizationResult: ...
```

`on_progress(msg)` 由 Streamlit 用 `st.empty().write(msg)` 接收即時進度。

---

## §5 收斂判定邏輯

```
no_improve_count = 0
best_score = Phase1 最佳分數

for round in range(max_rounds):
    suggestions = LLM 建議（3 組）
    if 解析失敗 or 沒有新組合:
        stopped_reason = "no_new_suggestions"; break

    for params in suggestions:
        score = 回測 + composite_score
        if score > best_score + converge_threshold:
            best_score = score
            no_improve_count = 0
        else:
            no_improve_count += 1

    if no_improve_count >= patience:
        stopped_reason = "converged"; break
else:
    stopped_reason = "max_rounds"
```

**注意：** `no_improve_count` 按「單次測試」而非「整輪」累加，patience=2 代表連續 2 次測試都無改善即停。

---

## §6 Streamlit UI 整合

現有頁面以 `st.tabs(["回測", "自動優化"])` 切分。

**「自動優化」頁：**
1. **搜尋範圍輸入**（依 strategy_type 切換）：
   - Grid：`price_lower_min/max`、`price_upper_min/max`、`grid_num` multiselect（候選值 [4,6,8,10]）
   - VA：`total_periods` range、`interval_days` range
2. `max_rounds` slider（1–10，預設 5）
3. "啟動優化" 按鈕 → `runner.run_optimization(on_progress=...)`
4. **進度顯示**：`st.empty()` 逐筆更新，顯示「第 N 輪 / 已測 M 組 / 目前最佳 {score:.4f}」
5. **結果表格**：`st.dataframe` 顯示所有 `RoundRecord`（來源輪次、參數、score、total_return、mdd、win_rate），按 score 降序，第一列高亮
6. "套用此參數" 按鈕：把選取列的參數寫入 `st.session_state`，切換到回測頁自動填入

UI 層不直接呼叫引擎；由 `app/runner.py` 新增 `run_optimization(config, engine, provider, on_progress)` 包裝，保持薄殼原則。

---

## §7 測試策略

檔案：`tests/test_optimizer.py`

| 測試 | 方式 | 驗證點 |
|---|---|---|
| `test_composite_score_weights` | 純算術 | 已知數值算出預期 score |
| `test_composite_score_min_trades` | 純算術 | trade_count < 3 → -999 |
| `test_phase1_returns_top_k` | mock engine（回傳固定 result）| Top-K 按 score 降序，長度 = K |
| `test_phase2_llm_parsed` | FakeProvider 回傳合法 JSON | 正確解析並跑回測 |
| `test_phase2_llm_parse_fail` | FakeProvider 回傳亂碼 | stopped_reason = "no_new_suggestions"，不 raise |
| `test_convergence_stops` | mock engine 回傳固定 score | patience 輪後 stopped_reason = "converged" |
| `test_max_rounds_stops` | mock engine 每輪小幅提升 | stopped_reason = "max_rounds" |
| `test_e2e_offline` | CsvProvider fixture + OfflineProvider + 真實引擎 | Phase1 完成，best_params 非空，OptimizationResult 合法 |

**不測 Streamlit 層**（依既有慣例）；只測 `runner.run_optimization()` 的邏輯分支，覆蓋 provider 分支 + on_progress 回調有被呼叫。
