# Python 學習閱讀地圖

這份專案可以照「資料 → 規則 → 流程 → 介面」的順序讀。先不要急著看 Streamlit UI，先把純 Python 的核心讀懂。

## 1. 先看資料長相

檔案：`src/backtesting_copilot/models.py`

你會學到：

- `Enum`：固定選項，例如策略類型、買賣方向。
- `dataclass`：快速定義資料物件，例如 `Bar`、`Trade`、`BacktestResult`。
- 型別註記：例如 `list[Trade]`、`GridParams | None`。
- `field(default_factory=list)`：避免多個物件共用同一個 list。

建議先問自己：一筆 K 棒資料、一筆交易紀錄、一份回測結果各有哪些欄位？

## 2. 再看資料從哪裡來

檔案：

- `src/backtesting_copilot/data/provider.py`
- `src/backtesting_copilot/data/csv_provider.py`
- `src/backtesting_copilot/data/yfinance_provider.py`

你會學到：

- `Protocol`：用來描述「資料來源應該提供哪些方法」。
- `Path`：比手動串字串更安全的路徑處理。
- `pandas`：讀 CSV 並轉成專案自己的 `Bar` 物件。
- 例外處理：資料不存在時丟出 `DataUnavailableError`。

建議先讀 `provider.py`，再讀 CSV 版本；yfinance 版本最後再看。

## 3. 看策略公式

檔案：

- `src/backtesting_copilot/strategies/grid.py`
- `src/backtesting_copilot/strategies/value_averaging.py`

你會學到：

- 小函式設計：`should_buy()`、`should_sell()` 只回答一件事。
- `range()`、`for` 迴圈、`timedelta` 日期加減。
- `min()` 同時套多個上限。

這一層只管策略規則，不管資料下載、手續費、風控或 UI。

## 4. 看風控與績效指標

檔案：

- `src/backtesting_copilot/risk/engine.py`
- `src/backtesting_copilot/backtest/metrics.py`

你會學到：

- 如何用布林值累積規則判斷。
- 最大回撤 `max_drawdown()` 如何從 equity curve 算出來。
- 為什麼一些函式會先做防禦式檢查。

## 5. 最後看主流程

檔案：

- `src/backtesting_copilot/backtest/engine.py`
- `src/backtesting_copilot/app/runner.py`

你會學到：

- 類別如何保存依賴，例如 `BacktestEngine(data_provider, risk_engine)`。
- 如何逐根 K 棒模擬時間前進。
- 私有方法命名慣例：`_run_grid()`、`_build_result()`。
- 如何把多個模組接成一條 pipeline。

讀 `engine.py` 時可以先抓住一個主軸：每天讀一根 bar，先做風控，再決定買賣，最後更新帳戶價值。

## 6. AI 分析層

檔案：`src/backtesting_copilot/ai/analyst.py`

你會學到：

- 依賴注入：把 provider 當參數傳入。
- 離線 fallback：沒有 LLM 時仍能產生規則式分析。
- `try/except`：外部服務失敗時不讓主流程中斷。

搭配閱讀：`docs/learn/first-class-functions-and-dependency-injection.md`

## 小練習

1. 在 `tests/fixtures/E2E.csv` 裡挑一天價格，手算 `should_buy()` 會不會觸發。
2. 把 `grid_num` 改成 3，追蹤 `generate_grid_levels()` 產生哪些買賣價。
3. 用一個很短的 `equity_curve = [100, 110, 99, 120]` 手算最大回撤，再對照 `max_drawdown()`。
4. 在 `run_backtest()` 裡放中斷點或 `print()`，觀察 result、report、trades_csv 分別是什麼。
