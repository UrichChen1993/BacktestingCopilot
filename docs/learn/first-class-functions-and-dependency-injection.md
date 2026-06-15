# Python 一等公民：函式與類別當變數傳入

> 對應程式碼：`src/backtesting_copilot/ai/analyst.py`

---

## 核心概念

Python 裡，函式和類別本身就是物件，可以像變數一樣傳來傳去，這叫「一等公民（first-class citizen）」。

---

## 傳入類別實例 vs 類別本身

```python
# 傳入「實例」（加括號 → 先建立，再傳入）
provider = OfflineProvider()

# 傳入「類別本身」（不加括號 → 讓函式內部決定何時建立）
def make(cls):
    return cls()   # 函式內才建立實例

make(OfflineProvider)
```

在 `analyst.py` 裡，`provider` 收到的是**實例**：

```python
def analyze_backtest(
    result: BacktestResult,
    *,
    provider: LLMProvider | None = None,  # 傳入已建立好的實例
) -> BacktestReport:
    provider = provider or OfflineProvider()  # None 時才自己建一個
```

---

## isinstance：確認物件身份

```python
if isinstance(provider, OfflineProvider):
    return ""
```

`isinstance(物件, 類別)` 回答「這個物件是不是這個類別生出來的？」  
是 → `True`；否 → `False`。

這裡用來判斷：「有沒有真正的 LLM？」

---

## 依賴注入（Dependency Injection）

這個設計讓呼叫端決定「要用哪個 LLM」，函式本身不在乎：

```python
# 測試時：離線，不打 API
report = analyze_backtest(result)

# 正式環境：換成真正的 Gemini
report = analyze_backtest(result, provider=GeminiProvider(api_key="..."))
```

**好處**：
- 測試不需要真的打 API（快、穩定、不花錢）
- 換 LLM 廠商不用修改 `analyze_backtest` 的邏輯

---

## 最簡單的類比：函式當變數

```python
def greet(name):
    print(f"Hello {name}")

def run(fn, value):   # fn 是函式，當變數傳入
    fn(value)

run(greet, "Alice")   # 輸出：Hello Alice
```

`fn` 和 `greet` 沒有本質差別，`fn` 只是個「還不知道叫什麼名字」的佔位符。

---

## 小結

| 寫法 | 意思 |
|------|------|
| `OfflineProvider()` | 建立實例（呼叫類別） |
| `OfflineProvider` | 類別本身（可當變數傳） |
| `isinstance(x, T)` | 確認 x 是否為 T 的實例 |
| 函式當參數傳入 | 讓呼叫端決定「做什麼」，函式決定「何時做」 |
