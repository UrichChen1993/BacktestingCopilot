# RNN 市場狀態分類器（區間 vs 趨勢）— 設計文件

- 日期：2026-06-15
- 來源：使用者構想「讓上下區間透過 RNN + LLM 分析」，經 brainstorming 收斂
- 關聯：[2026-06-09-backtesting-copilot-mvp-design.md](2026-06-09-backtesting-copilot-mvp-design.md)
- 範圍：新增一個**可插拔的實驗模組**，用 RNN 判斷「目前是否適合網格（區間盤 vs 趨勢盤）」，強化 `advisor` 的策略選擇。**不接實單、不預測價格方向。**

## 1. 動機與現況

目前上下區間（`price_lower` / `price_upper`）由 [advisor.py:54-58](../../../src/backtesting_copilot/ai/advisor.py#L54-L58) 用「近 40 日高 / 低」直接決定；是否選網格則靠 [advisor.py:46-47](../../../src/backtesting_copilot/ai/advisor.py#L46-L47) 的 `range_ok and flat_trend` 簡單規則（`range_pct_40` 與 60MA 斜率）。

本模組用 RNN 取代/強化「`flat_trend`」這個判斷 —— 學習「現在像不像區間盤」。**上下區間的數字仍由 40 日高低決定，RNN 不碰價位。**

## 2. 設計原則（沿用 MVP §17）

- RNN 只輸出「適不適合網格」的機率，**不預測漲跌方向**（避免違反 PRD §17「不得宣稱能預測方向」）。
- LLM 角色不變：只做白話解釋（narrative），不參與算數字。
- 守住 MVP 的離線確定性：模組預設關閉，缺套件 / 缺模型檔即自動 fallback 回現有統計規則。
- 確定性部分以 pytest 完整覆蓋；模型本身用注入假模型 / seed 固定的 smoke test。

## 3. 啟用與 Fallback

- 啟用條件（三者皆需滿足，否則 fallback）：
  1. 環境變數 `USE_RNN_REGIME=1`
  2. 已安裝 `torch`（optional 相依）
  3. 模型檔存在於 `artifacts/regime/`
- 任一不滿足 → `advisor` 走現有 `range_ok and flat_trend` 邏輯，行為與現在完全一致。

## 4. 套件結構（新增 `ml/`，與 `ai/` 分開，因為它不是 LLM）

```
src/backtesting_copilot/ml/
  __init__.py
  labeling.py      # 規則自動標註（純函式，可測）
  dataset.py       # bars → 序列樣本 (X, y)（純函式，可測）
  model.py         # LSTM 分類器定義（torch，optional import）
  classifier.py    # RegimeClassifier：載入模型、predict_proba(bars) -> float
  train.py         # CLI 訓練腳本：輸出 model artifact + metrics + baseline 對照
artifacts/regime/  # 訓練好的模型檔（gitignore；缺檔即 fallback）
```

## 5. 規則自動標註（`labeling.py`）

對每個時間點 `t`，看**未來 H 天（預設 20）**：

- 淨變動 `net = |close[t+H] / close[t] - 1|`
- 區間波動 `osc = (max(close[t..t+H]) - min(close[t..t+H])) / close[t]`
- 標籤：
  - `net < TREND_THRESH(預設 0.08)` 且 `osc >= MIN_OSC(預設 0.06)` → **label = 1（區間，適合網格）**
  - 否則 → **label = 0（趨勢 / 不適合）**
- 所有閾值為參數；標註為純函式 → pytest 完整覆蓋。
- 資料尾端不足 H 天的樣本捨棄（不可用未來資料以外的洩漏）。

## 6. 模型與輸入（`model.py` / `dataset.py`）

- 輸入：過去 **40 根 bar** 的特徵序列。每根 bar 的特徵（正規化後）：
  - 日報酬 `close[i]/close[i-1] - 1`
  - `range_pct = (high-low)/close`
  - `atr_14 / close`
  - `ma_60` 斜率代理（不足 60 根時以 0 或遮罩處理）
- 模型：單層 LSTM → linear → sigmoid，輸出 `P(區間) ∈ [0,1]`。刻意做小（實驗用、快訓練）。
- `dataset.py` 負責把連續 bars 切成 `(序列窗口, 標籤)`；窗口化與正規化為純函式，可測。

## 7. 整合點（改 `advisor.py`，最小侵入）

`recommend_strategy()` 新增 optional 參數 `classifier: RegimeClassifier | None` 與 `bars`（序列）：

- classifier 存在且啟用：
  - 取 `p = classifier.predict_proba(bars)`
  - 以 `range_ok and p >= 0.5` 決定是否選 GRID（取代 `flat_trend`）
  - `p` 映射到 `confidence_level`（例：p≥0.7 → HIGH，0.5–0.7 → MEDIUM，<0.5 → LOW）
  - `reason` 加入「RNN 判定為區間盤（信心 p）」
- classifier 為 `None`（預設）→ 完全走現有邏輯。
- **選了 GRID 後，`price_lower/upper` 仍用 `features.low_40 / high_40`**（區間數字不變）。

## 8. 測試策略（守住 MVP §9）

- 確定性、必測：
  - `labeling`（各閾值邊界）
  - `dataset` 窗口化與正規化、尾端不足樣本捨棄
  - `advisor` 用**注入的 fake classifier** 驗證整合邏輯（選 GRID / 不選 / confidence 映射 / fallback）
  - Fallback 路徑（無 env / 無 torch / 無模型檔）
- 模型本身：seed 固定的「迷你 fixture 訓練」smoke test，或注入假模型；**不依賴真實 torch 訓練結果**。
- Baseline 守門：`train.py` 同時報告「RNN vs 現有 slope 規則」在同一份資料上的準確率；RNN 未顯著勝出則不啟用。

## 9. 資料來源

沿用現有 yfinance / CSV provider 抓歷史 OHLCV 當訓練集；單一標的起步，可擴充多標的。

## 10. 預設參數彙整

| 項目 | 預設 |
| --- | --- |
| 框架 | PyTorch（optional 相依） |
| 未來視窗 H | 20 天 |
| 趨勢閾值 TREND_THRESH | 0.08 |
| 最小波動 MIN_OSC | 0.06 |
| 輸入回看窗口 | 40 根 bar |
| 啟用旗標 | `USE_RNN_REGIME=1` |
| 模型檔位置 | `artifacts/regime/`（gitignore） |

## 11. 明確排除（非本次）

- RNN 直接預測未來最高/最低價（方向性價格預測，違反 §17）。
- RNN 估「波動帶寬」直接決定區間寬度（保留為後續迭代）。
- 多標的聯合訓練、線上學習、自動再訓練排程。
- 將 RNN 結果寫入正式設定或繞過 validator / RiskEngine。
