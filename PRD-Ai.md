# 產品需求文件 PRD

# AI 雙軌資金配置與回測決策系統

## AI Dual-Strategy Asset Allocation & Backtesting Copilot

---

## 1. 文件概述

### 1.1 專案名稱

**AI 雙軌資金配置與回測決策系統**
AI Dual-Strategy Asset Allocation & Backtesting Copilot

---

### 1.2 專案目標

建立一套針對 **1–2 個月短線波段週期** 的 AI 輔助量化策略系統，整合：

1. **波動套利網格策略**
2. **動態價值平均策略**
3. **AI 策略分析與參數建議**
4. **回測分析與績效報告**
5. **風險控管與異常提醒**

本系統的核心目標不是預測股價方向，而是透過數學規則、資金配置、風控濾網與 AI 分析，協助使用者降低主觀判斷錯誤，提升短線資金配置效率。

---

### 1.3 核心產品定位

本產品不是「AI 自動預測漲跌系統」，而是：

> **AI 輔助的量化策略決策與回測工具。**

系統定位如下：

| 層級     | 角色            |
| ------ | ------------- |
| 策略引擎   | 負責根據公式產生買賣訊號  |
| 風控引擎   | 負責阻擋高風險交易     |
| AI 分析層 | 負責解釋、建議、比較與提醒 |
| 使用者    | 負責最後確認與策略啟動   |

---

## 2. 產品背景與痛點

### 2.1 使用者痛點

1. **不想猜市場方向**

   * 短線市場容易受消息、籌碼與情緒影響。
   * 主觀判斷容易追高殺低。

2. **想利用波動賺取價差**

   * 當標的處於區間震盪時，希望透過網格策略自動低買高賣。

3. **想控制平均成本**

   * 傳統定期定額在短週期內無法有效根據價格波動調整投入金額。
   * 使用者希望跌多買多、漲多買少。

4. **回測後缺乏解讀能力**

   * 一般使用者即使看到報酬率、MDD、勝率，也不一定知道策略是否健康。

5. **擔心自動交易風險**

   * 若直接讓 AI 下單，可能產生不可控風險。
   * 需要明確風控與人工確認機制。

---

## 3. 產品總體架構

### 3.1 系統架構

```text
使用者輸入
  ↓
AI 意圖解析與策略建議
  ↓
參數驗證器 Parameter Validator
  ↓
策略引擎 Strategy Engine
  ├─ 模組 A：波動套利網格 Grid Trading
  └─ 模組 B：動態價值平均 Value Averaging
  ↓
風控引擎 Risk Engine
  ↓
回測引擎 Backtesting Engine
  ↓
AI 回測分析與報告產生
  ↓
使用者確認
  ↓
模擬交易 / 半自動下單 / 全自動下單
```

---

### 3.2 AI 使用原則

本系統中的 AI 僅能執行以下任務：

1. 解析使用者自然語言需求。
2. 建議適合使用網格策略或價值平均策略。
3. 根據歷史資料摘要提出參數建議。
4. 解讀回測結果。
5. 提醒策略風險。
6. 產生自然語言報告。
7. 協助比較不同參數組合。

AI 不可執行以下行為：

1. 不可直接繞過風控下單。
2. 不可自行提高資金上限。
3. 不可自行關閉風控條件。
4. 不可在未經使用者確認下進行實單交易。
5. 不可保證獲利。
6. 不可宣稱能預測市場方向。

---

## 4. 使用者角色

### 4.1 一般投資使用者

需求：

* 輸入標的、資金與週期。
* 想知道適合網格還是價值平均法。
* 想看回測結果與 AI 解釋。
* 不一定具備程式或量化背景。

---

### 4.2 進階量化使用者

需求：

* 自訂網格層數、價格區間、扣款週期。
* 比較不同策略參數。
* 匯出交易紀錄。
* 後續可能串接券商 API。

---

### 4.3 系統管理者 / 開發者

需求：

* 管理資料來源。
* 管理策略參數限制。
* 查看系統錯誤與 API 狀態。
* 追蹤策略執行紀錄。

---

## 5. 核心功能模組

---

# 5.1 模組 A：波動套利網格策略 Grid Trading Module

## 5.1.1 使用場景

當使用者認為標的在未來 1–2 個月內不會出現單邊大跌，而是可能在某個價格區間內上下震盪時，使用網格策略。

適合情境：

* 標的處於盤整區間。
* 波動率足夠。
* 無明顯重大利空。
* 大盤未觸發系統性風控。

---

## 5.1.2 輸入參數

| 參數                      | 說明       | 範例         |
| ----------------------- | -------- | ---------- |
| `symbol`                | 股票代號     | 2330.TW    |
| `total_capital`         | 本策略總資金   | 100,000    |
| `price_upper`           | 網格區間上限   | 112        |
| `price_lower`           | 網格區間下限   | 100        |
| `grid_num`              | 網格層數     | 6          |
| `start_date`            | 策略開始日期   | 2026-06-01 |
| `end_date`              | 策略結束日期   | 2026-07-31 |
| `fee_rate`              | 手續費率     | 0.001425   |
| `tax_rate`              | 交易稅率     | 0.003      |
| `market_filter_enabled` | 是否啟用大盤風控 | true       |

---

## 5.1.3 核心公式

### 網格間距

```text
Grid_Space = (Price_Upper - Price_Lower) / Grid_Num
```

### 每格資金

```text
Unit_Capital = Total_Capital / Grid_Num
```

### 每格買入股數

```text
Quantity = floor(Unit_Capital / Buy_Price)
```

---

## 5.1.4 網格節點產生邏輯

假設：

```text
Price_Lower = 100
Price_Upper = 112
Grid_Num = 6
Grid_Space = 2
```

產生節點：

| Level | Buy Price | Sell Price |
| ----- | --------: | ---------: |
| 1     |       100 |        102 |
| 2     |       102 |        104 |
| 3     |       104 |        106 |
| 4     |       106 |        108 |
| 5     |       108 |        110 |
| 6     |       110 |        112 |

---

## 5.1.5 交易觸發邏輯

### 買進條件

當現價下跌觸碰某一層 `buy_price`，且該層狀態為 `WAIT_BUY`，則觸發買進。

```text
if current_price <= buy_price and grid_status == WAIT_BUY:
    create_buy_signal()
```

---

### 賣出條件

當現價上漲觸碰該層對應 `sell_price`，且該層狀態為 `HOLDING`，則觸發賣出。

```text
if current_price >= sell_price and grid_status == HOLDING:
    create_sell_signal()
```

---

## 5.1.6 網格狀態

每一格需要記錄狀態，避免重複買賣。

```text
WAIT_BUY：等待買進
HOLDING：已買進，等待賣出
SOLD：已賣出，完成一輪套利
DISABLED：被風控停用
```

---

## 5.1.7 網格資料結構

```json
{
  "grid_id": "G001",
  "strategy_id": "S001",
  "level": 1,
  "buy_price": 100,
  "sell_price": 102,
  "unit_capital": 16666,
  "quantity": 166,
  "status": "WAIT_BUY",
  "buy_order_id": null,
  "sell_order_id": null,
  "realized_profit": 0
}
```

---

# 5.2 模組 B：動態價值平均策略 Value Averaging Module

## 5.2.1 使用場景

當使用者想在 1–2 個月內分批投入資金，並希望系統根據市場價格變化自動調整投入金額時，使用價值平均策略。

適合情境：

* 想分批布局。
* 不想一次買滿。
* 想在下跌時加大投入。
* 想在上漲時減少投入。
* 可接受短期浮動。

---

## 5.2.2 輸入參數

| 參數                     | 說明        | 範例         |
| ---------------------- | --------- | ---------- |
| `symbol`               | 股票代號      | 2330.TW    |
| `total_capital`        | 總資金       | 100,000    |
| `total_periods`        | 總扣款次數     | 4          |
| `period_interval_days` | 每期間隔天數    | 14         |
| `target_step`          | 每期目標市值增加額 | 25,000     |
| `max_order_multiplier` | 單期最大加碼倍數  | 2          |
| `negative_order_mode`  | 負投入處理模式   | SKIP       |
| `start_date`           | 策略開始日期    | 2026-06-01 |
| `end_date`             | 策略結束日期    | 2026-07-31 |

---

## 5.2.3 核心公式

### 每期目標資產增加額

```text
Target_Step = Total_Capital / Total_Periods
```

### 第 t 期目標市值

```text
Target_Value_t = Target_Step × t
```

### 第 t 期應投入金額

```text
Raw_Order_Size_t = Target_Value_t - Current_Value_t
```

### 加入單期最大投入限制

```text
Max_Order_Size = Target_Step × Max_Order_Multiplier
```

### 實際下單金額

```text
Order_Size_t = min(Raw_Order_Size_t, Max_Order_Size, Remaining_Cash)
```

---

## 5.2.4 下單邏輯

### 情境一：股價下跌

若目前庫存市值低於目標市值，系統提高本期投入金額。

```text
if Raw_Order_Size_t > Target_Step:
    action = "加碼買進"
```

---

### 情境二：股價上漲

若目前庫存市值接近或高於目標市值，系統減少投入。

```text
if 0 < Raw_Order_Size_t < Target_Step:
    action = "減少扣款"
```

---

### 情境三：漲幅過大

若計算結果為負數，代表目前市值已超過目標。

可選模式：

| 模式                    | 說明      |
| --------------------- | ------- |
| `SKIP`                | 不扣款、不賣出 |
| `TAKE_PROFIT_PARTIAL` | 小幅獲利了結  |
| `REBALANCE`           | 賣出至目標市值 |

MVP 建議採用：

```text
negative_order_mode = SKIP
```

---

# 5.3 AI 策略顧問模組 AI Strategy Advisor

## 5.3.1 功能目標

AI Strategy Advisor 負責根據使用者輸入、歷史價格特徵與回測摘要，建議使用者採用哪一種策略。

---

## 5.3.2 輸入資料

| 類別    | 資料                     |
| ----- | ---------------------- |
| 使用者輸入 | 標的、資金、週期、風險偏好          |
| 價格資料  | 20 日高低點、40 日高低點、60 日均線 |
| 波動資料  | ATR、標準差、區間振幅           |
| 趨勢資料  | 均線斜率、價格相對均線位置          |
| 回測資料  | 報酬率、MDD、交易次數、勝率        |

---

## 5.3.3 輸出內容

AI 輸出格式：

```json
{
  "recommended_strategy": "GRID",
  "confidence_level": "MEDIUM",
  "reason": [
    "近 40 日價格呈現區間震盪",
    "波動率足以支撐網格交易",
    "目前大盤風控未觸發"
  ],
  "suggested_parameters": {
    "price_lower": 100,
    "price_upper": 112,
    "grid_num": 6,
    "total_capital": 100000
  },
  "risk_notes": [
    "若跌破區間下緣，應暫停加碼",
    "建議啟用 60MA 大盤濾網"
  ]
}
```

---

## 5.3.4 AI 建議限制

AI 只能提供建議，不可直接寫入正式策略設定。
所有 AI 建議都必須經過：

1. Parameter Validator
2. Risk Engine
3. User Confirmation

---

# 5.4 AI 參數建議模組 AI Parameter Suggestion

## 5.4.1 功能目標

根據歷史價格與波動資料，自動產生建議參數。

---

## 5.4.2 網格策略參數建議

系統先計算：

```text
- 20 日最高價
- 20 日最低價
- 40 日最高價
- 40 日最低價
- ATR
- 成交量密集區
- 均線位置
```

AI 再產生建議：

```text
建議採用近 40 日主要交易區間作為網格上下緣。
若波動率過低，降低網格層數。
若波動率過高，增加網格層數但降低單格資金。
```

---

## 5.4.3 價值平均策略參數建議

系統根據總資金與週期產生：

```text
Total_Periods = 4
Target_Step = Total_Capital / 4
Max_Order_Multiplier = 2
Negative_Order_Mode = SKIP
```

AI 再補充說明：

```text
目前標的波動偏高，建議保留單期最大投入限制，避免一次加碼過多。
```

---

# 5.5 AI 回測分析模組 AI Backtest Analyst

## 5.5.1 功能目標

將回測結果轉換成使用者可理解的策略分析報告。

---

## 5.5.2 回測輸入

```json
{
  "strategy_type": "GRID",
  "symbol": "2330.TW",
  "start_date": "2026-04-01",
  "end_date": "2026-05-31",
  "total_capital": 100000,
  "final_value": 103200,
  "total_return": 0.032,
  "mdd": -0.085,
  "win_rate": 0.64,
  "trade_count": 18,
  "cash_usage_rate": 0.82
}
```

---

## 5.5.3 AI 輸出報告

AI 應產生以下內容：

1. 策略總結
2. 績效摘要
3. 風險摘要
4. 參數是否合理
5. 是否適合進入模擬交易
6. 建議調整方向

---

## 5.5.4 AI 報告範例

```text
本次網格策略回測報酬率為 3.2%，最大回撤為 -8.5%，交易勝率為 64%。

策略在震盪期間具備一定套利效果，但最大回撤偏高，代表若標的跌破區間下緣，可能產生較大浮虧。

建議：
1. 將網格層數由 6 層提高至 8 層，降低單筆投入。
2. 啟用大盤 60MA 風控。
3. 設定跌破 Price_Lower 後停止新增買進。
4. 先進入 Paper Trading，不建議直接實單。
```

---

# 5.6 風控引擎 Risk Engine

## 5.6.1 功能目標

風控引擎負責阻擋高風險交易，且優先級高於 AI 建議與策略引擎。

---

## 5.6.2 風控規則一：大盤系統性風險煞車

### 條件

```text
大盤指數跌破 60MA
且 60MA 斜率向下
```

### 行為

```text
暫停所有買進與加碼指令
允許賣出與停利
策略狀態改為 PAUSED_BY_MARKET
通知使用者
```

---

## 5.6.3 風控規則二：跌破策略區間

### 條件

```text
current_price < price_lower
```

### 行為

```text
停止新增網格買進
保留既有持倉
通知使用者是否重設網格區間
```

---

## 5.6.4 風控規則三：最大資金使用率

### 條件

```text
used_capital / total_capital >= max_cash_usage_rate
```

### 預設值

```text
max_cash_usage_rate = 0.9
```

### 行為

```text
停止新增買進
保留至少 10% 現金
```

---

## 5.6.5 風控規則四：最大回撤限制

### 條件

```text
current_drawdown <= max_drawdown_limit
```

### 預設值

```text
max_drawdown_limit = -10%
```

### 行為

```text
暫停策略
通知使用者
等待人工確認
```

---

## 5.6.6 風控規則五：時間強制結算

### 條件

```text
current_date >= end_date
```

### 行為

```text
停止自動循環
產生結算報告
由使用者決定：
1. 清倉
2. 轉長線持有
3. 延長策略週期
4. 重新回測
```

---

## 5.6.7 風控規則六：API / 資料異常

### 條件

```text
券商 API 中斷
價格資料延遲
帳戶餘額讀取失敗
委託回報異常
```

### 行為

```text
停止自動下單
策略狀態改為 PAUSED_BY_ERROR
發送 Email / LINE / Telegram 通知
等待人工處理
```

---

# 5.7 參數驗證器 Parameter Validator

## 5.7.1 功能目標

所有 AI 建議與使用者輸入都必須經過參數驗證器，避免不合理參數進入策略引擎。

---

## 5.7.2 驗證規則

| 參數               | 驗證規則               |
| ---------------- | ------------------ |
| `total_capital`  | 不可超過使用者設定上限        |
| `grid_num`       | 建議 6–10，MVP 上限 12  |
| `price_upper`    | 必須大於 `price_lower` |
| `price_lower`    | 不可距離現價過遠           |
| `unit_capital`   | 必須大於最低交易金額         |
| `max_order_size` | 不可超過剩餘現金           |
| `end_date`       | 不可超過策略允許週期         |
| `symbol`         | 必須存在於資料源           |

---

## 5.7.3 驗證失敗回覆範例

```json
{
  "valid": false,
  "errors": [
    "grid_num = 20 超過 MVP 上限 12",
    "price_lower 距離現價超過 20%，風險過高",
    "unit_capital 低於最低交易金額"
  ],
  "suggested_fix": {
    "grid_num": 8,
    "price_lower": 102
  }
}
```

---

# 5.8 策略狀態機 Strategy State Machine

## 5.8.1 狀態定義

```text
INIT：策略初始化
READY：參數驗證通過，等待啟動
RUNNING：策略執行中
PAUSED_BY_MARKET：大盤風控暫停
PAUSED_BY_ERROR：系統錯誤暫停
PAUSED_BY_USER：使用者手動暫停
EXPIRED：策略週期結束
CLOSED：策略已結束
```

---

## 5.8.2 狀態轉移

```text
INIT → READY
READY → RUNNING
RUNNING → PAUSED_BY_MARKET
RUNNING → PAUSED_BY_ERROR
RUNNING → PAUSED_BY_USER
RUNNING → EXPIRED
EXPIRED → CLOSED
PAUSED_BY_USER → RUNNING
PAUSED_BY_MARKET → RUNNING
```

---

# 6. 回測功能需求

## 6.1 MVP 回測範圍

MVP 僅需支援：

```text
1. 單一標的
2. 單一策略
3. 歷史資料回測
4. 不接實單 API
5. 產生交易明細
6. 產生績效報表
7. 產生 AI 分析報告
```

---

## 6.2 回測輸入

| 參數                | 說明                     |
| ----------------- | ---------------------- |
| `symbol`          | 股票代號                   |
| `strategy_type`   | GRID / VALUE_AVERAGING |
| `start_date`      | 回測開始日期                 |
| `end_date`        | 回測結束日期                 |
| `initial_capital` | 初始資金                   |
| `fee_rate`        | 手續費                    |
| `tax_rate`        | 交易稅                    |
| `strategy_params` | 策略參數                   |

---

## 6.3 回測輸出

| 指標                    | 說明     |
| --------------------- | ------ |
| `final_value`         | 期末總資產  |
| `total_return`        | 總報酬率   |
| `mdd`                 | 最大回撤   |
| `realized_profit`     | 已實現損益  |
| `unrealized_profit`   | 未實現損益  |
| `trade_count`         | 交易次數   |
| `win_rate`            | 勝率     |
| `cash_usage_rate`     | 資金使用率  |
| `remaining_cash`      | 剩餘現金   |
| `holding_quantity`    | 剩餘持股   |
| `avg_cost`            | 平均成本   |
| `market_filter_count` | 風控觸發次數 |

---

## 6.4 回測績效判斷標準

系統應至少提供以下判斷：

```text
若報酬率為正且 MDD 可控：
    策略可進入模擬交易

若報酬率為正但 MDD 過高：
    需要降低單筆投入或重新設定區間

若報酬率為負且交易次數少：
    標的不適合網格策略

若資金使用率過高但報酬有限：
    策略效率不佳

若風控頻繁觸發：
    目前市場不適合短線自動策略
```

---

# 7. 通知與告警功能

## 7.1 通知渠道

MVP 支援：

```text
Email
LINE Messaging API
Telegram Bot
```

---

## 7.2 通知類型

| 類型     | 說明            |
| ------ | ------------- |
| 策略啟動通知 | 策略開始執行        |
| 買進訊號通知 | 產生買進訊號        |
| 賣出訊號通知 | 產生賣出訊號        |
| 風控通知   | 大盤濾網、MDD、跌破區間 |
| 錯誤通知   | API、資料、資金異常   |
| 到期通知   | 策略週期結束        |
| 回測報告通知 | 回測完成並附報告      |

---

## 7.3 通知格式範例

```text
【策略風控提醒】

標的：2330.TW
策略：GRID
狀態：PAUSED_BY_MARKET

原因：
大盤跌破 60MA，且均線斜率向下。

系統行為：
已暫停新增買進指令。
既有持倉保留。
賣出停利仍可執行。

建議：
等待大盤重新站回 60MA 後，再評估是否恢復策略。
```

---

# 8. 資料來源需求

## 8.1 歷史資料

MVP 可使用：

```text
yfinance
FinMind
券商歷史資料 API
CSV 手動匯入
```

---

## 8.2 即時資料

網格策略若進入模擬交易或實單階段，需要：

```text
1 分 K 資料
或 Tick 報價資料
```

價值平均策略僅需：

```text
日收盤價
扣款日價格
```

---

## 8.3 帳戶資料

進入 V3 後需串接：

```text
現金餘額
持股數量
平均成本
已實現損益
未實現損益
委託狀態
成交回報
```

---

# 9. 非功能需求

## 9.1 可用性

```text
MVP 可採本機執行。
V2 後建議部署至雲端。
系統需保留完整交易與回測紀錄。
```

---

## 9.2 穩定性

```text
資料抓取失敗時不可產生交易訊號。
API 異常時自動切換為手動安全模式。
風控引擎不可被 AI 覆蓋。
```

---

## 9.3 可追溯性

所有策略建議與下單訊號都必須記錄：

```text
時間
策略 ID
參數
觸發原因
AI 建議內容
風控檢查結果
使用者確認狀態
```

---

## 9.4 安全性

```text
API Key 不可明碼儲存。
實單交易需二次確認。
全自動交易需設定每日最大損失。
使用者需自行設定最大資金上限。
```

---

# 10. 資料表設計草案

## 10.1 strategy_config

```sql
CREATE TABLE strategy_config (
    strategy_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    total_capital REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL,
    market_filter_enabled BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## 10.2 grid_levels

```sql
CREATE TABLE grid_levels (
    grid_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    level INTEGER NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    unit_capital REAL NOT NULL,
    quantity INTEGER,
    status TEXT NOT NULL,
    buy_order_id TEXT,
    sell_order_id TEXT,
    realized_profit REAL DEFAULT 0,
    created_at TEXT NOT NULL
);
```

---

## 10.3 value_averaging_schedule

```sql
CREATE TABLE value_averaging_schedule (
    schedule_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    period_index INTEGER NOT NULL,
    target_value REAL NOT NULL,
    current_value REAL,
    raw_order_size REAL,
    final_order_size REAL,
    status TEXT NOT NULL,
    execute_date TEXT NOT NULL
);
```

---

## 10.4 trade_logs

```sql
CREATE TABLE trade_logs (
    trade_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    amount REAL NOT NULL,
    fee REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    reason TEXT,
    created_at TEXT NOT NULL
);
```

---

## 10.5 ai_reports

```sql
CREATE TABLE ai_reports (
    report_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    input_summary TEXT,
    ai_analysis TEXT,
    risk_notes TEXT,
    created_at TEXT NOT NULL
);
```

---

# 11. API 設計草案

## 11.1 建立策略

```http
POST /api/strategies
```

Request：

```json
{
  "symbol": "2330.TW",
  "strategy_type": "GRID",
  "total_capital": 100000,
  "start_date": "2026-06-01",
  "end_date": "2026-07-31",
  "params": {
    "price_lower": 100,
    "price_upper": 112,
    "grid_num": 6
  }
}
```

Response：

```json
{
  "strategy_id": "S001",
  "status": "READY",
  "validation_result": {
    "valid": true,
    "warnings": []
  }
}
```

---

## 11.2 執行回測

```http
POST /api/backtests
```

Request：

```json
{
  "symbol": "2330.TW",
  "strategy_type": "GRID",
  "initial_capital": 100000,
  "start_date": "2026-04-01",
  "end_date": "2026-05-31",
  "params": {
    "price_lower": 100,
    "price_upper": 112,
    "grid_num": 6
  }
}
```

Response：

```json
{
  "backtest_id": "B001",
  "final_value": 103200,
  "total_return": 0.032,
  "mdd": -0.085,
  "trade_count": 18,
  "win_rate": 0.64
}
```

---

## 11.3 產生 AI 報告

```http
POST /api/ai/reports
```

Request：

```json
{
  "backtest_id": "B001",
  "report_type": "BACKTEST_ANALYSIS"
}
```

Response：

```json
{
  "report_id": "R001",
  "summary": "本策略報酬率為 3.2%，但 MDD 偏高，建議降低單格資金。",
  "risk_level": "MEDIUM",
  "suggestions": [
    "網格層數由 6 提高至 8",
    "啟用大盤 60MA 風控",
    "先進入 Paper Trading"
  ]
}
```

---

## 11.4 取得策略狀態

```http
GET /api/strategies/{strategy_id}
```

Response：

```json
{
  "strategy_id": "S001",
  "symbol": "2330.TW",
  "strategy_type": "GRID",
  "status": "RUNNING",
  "used_capital": 82000,
  "remaining_cash": 18000,
  "unrealized_pnl": -3200,
  "realized_pnl": 1800
}
```

---

# 12. 使用者操作流程

## 12.1 AI 回測分析流程

```text
1. 使用者輸入標的、資金、週期
2. AI 解析需求
3. 系統取得歷史資料
4. 系統產生建議策略與參數
5. 使用者確認回測參數
6. 回測引擎執行
7. AI 產生回測分析報告
8. 使用者決定是否進入模擬交易
```

---

## 12.2 模擬交易流程

```text
1. 使用者選擇已通過回測的策略
2. 系統建立 Paper Trading 狀態
3. 系統根據即時或定時價格產生模擬訊號
4. 風控引擎檢查
5. 系統記錄模擬交易
6. AI 每日產生策略狀態摘要
```

---

## 12.3 半自動下單流程

```text
1. 策略引擎產生買賣訊號
2. 風控引擎檢查通過
3. AI 產生訊號說明
4. 使用者收到通知
5. 使用者按下確認
6. 系統送出券商 API 委託
7. 系統記錄成交結果
```

---

# 13. MVP 開發範圍

## 13.1 MVP 目標

第一版先完成：

```text
AI + 回測 + 策略建議 + 風控檢查
```

不做實單交易。

---

## 13.2 MVP 功能清單

| 功能             | 是否納入 MVP |
| -------------- | -------- |
| 單一標的回測         | 是        |
| 網格策略回測         | 是        |
| 價值平均策略回測       | 是        |
| AI 策略建議        | 是        |
| AI 回測分析報告      | 是        |
| 大盤 60MA 風控     | 是        |
| 交易紀錄輸出         | 是        |
| Streamlit 操作介面 | 是        |
| 實單 API 下單      | 否        |
| 多標的投組          | 否        |
| 全自動交易          | 否        |

---

## 13.3 MVP 技術建議

```text
Frontend：
Streamlit

Backend：
Python

Data：
yfinance / FinMind / CSV

Strategy：
pandas
numpy

Database：
SQLite

AI：
OpenAI API / Claude API

Notification：
Email / Telegram Bot
```

---

# 14. 開發階段規劃

## V1：AI 回測分析版

功能：

```text
- 手動輸入標的
- 自動抓歷史資料
- 網格策略回測
- 價值平均法回測
- AI 產生分析報告
- 匯出 CSV / Markdown 報告
```

---

## V2：AI 模擬交易版

功能：

```text
- 定時更新價格
- 模擬交易紀錄
- 每日策略摘要
- 風控提醒
- 通知系統
```

---

## V3：半自動下單版

功能：

```text
- 串接券商 API
- 產生下單建議
- 使用者確認後送單
- 成交回報紀錄
- 異常停止機制
```

---

## V4：全自動小額實驗版

功能：

```text
- 僅限小資金
- 每日最大虧損限制
- 強制風控
- 異常自動停止
- 定期 AI 報告
```

---

# 15. 成功指標 KPI

## 15.1 系統 KPI

| 指標          | 目標    |
| ----------- | ----- |
| 回測完成率       | > 95% |
| 資料抓取成功率     | > 95% |
| AI 報告產生成功率  | > 95% |
| 策略參數驗證覆蓋率   | 100%  |
| 風控阻擋異常交易覆蓋率 | 100%  |

---

## 15.2 策略分析 KPI

| 指標                 | 目的       |
| ------------------ | -------- |
| Total Return       | 衡量總績效    |
| MDD                | 衡量最大風險   |
| Cash Usage Rate    | 衡量資金使用效率 |
| Trade Count        | 衡量交易頻率   |
| Win Rate           | 衡量交易勝率   |
| Unrealized PnL     | 衡量浮虧風險   |
| Risk Trigger Count | 衡量風控啟動頻率 |

---

# 16. 風險與限制

## 16.1 投資風險

```text
本系統不保證獲利。
歷史回測不代表未來績效。
網格策略在單邊下跌時可能累積浮虧。
價值平均策略在連續下跌時可能快速消耗資金。
```

---

## 16.2 AI 風險

```text
AI 可能產生錯誤解讀。
AI 不可作為唯一決策來源。
AI 建議必須經過參數驗證與風控檢查。
AI 不可直接繞過使用者確認。
```

---

## 16.3 技術風險

```text
資料源可能延遲或錯誤。
券商 API 可能中斷。
回測結果可能受資料品質影響。
交易成本與滑價可能影響實際績效。
```

---

# 17. 結論

本系統的核心設計原則是：

```text
策略由數學規則執行
風控由硬規則把關
AI 負責分析與解釋
使用者保留最終決策權
```

第一階段建議先開發 **AI 回測分析 MVP**，透過歷史資料驗證網格策略與價值平均策略在不同市場情境下的表現。

待回測與模擬交易穩定後，再逐步進入半自動下單與小額全自動交易階段。

本產品最終目標不是打造一個「預測股價的 AI」，而是打造一個：

> **幫助使用者在不猜方向的前提下，紀律化配置資金、控制風險、解讀策略表現的 AI 量化助理。**
