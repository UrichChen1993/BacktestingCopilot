# 股市老猴 + 回測引擎整合設計

**日期：** 2026-06-20  
**範圍：** 個人工具  
**狀態：** 已通過設計審核

---

## 目標

在現有回測引擎（Grid / Value Averaging）旁邊，平行執行基本面分析（「股市老猴 v1」7 大檢查清單），最終合併兩份報告，給出「要不要用 Grid/VA 策略操作這檔股票」的綜合建議。

---

## 架構總覽

```
輸入：股票代號（2330.TW、AAPL、VOO…）
         │
         ├─────────────────────┬──────────────────────┐
         ▼                     ▼                      ▼
   結構化抓取              非結構化爬取           手動上傳
 yfinance + FinMind    公開資訊觀測站 +        PDF 法說會/
  財務三表、估值          MoneyDJ 新聞          研究報告
         │                     │                      │
         └─────────────────────┴──────────────────────┘
                               │
                  ┌────────────▼────────────┐
                  │   PostgreSQL + pgvector  │
                  │  documents（metadata）   │
                  │  document_chunks（文字） │
                  │  chunk_embeddings（向量）│
                  └────────────┬────────────┘
                               │ RAG 檢索
                  ┌────────────▼────────────┐
                  │  LLM + 股市老猴          │
                  │  7 大清單 Prompt         │
                  └────────────┬────────────┘
                               │ FundamentalReport
         ┌─────────────────────┤
         ▼                     ▼
   BacktestEngine         FundamentalReport
   （現有，平行跑）        7 張卡片 + 最終建議
         └─────────────────────┘
                    │ CombinedReport
                    ▼
             Streamlit UI
             新增「基本面」Tab + PDF 上傳
```

---

## 資料來源

| 類型 | 來源 | 說明 |
|------|------|------|
| 結構化財報 | yfinance | 財務三表、估值、股利 |
| 結構化財報 | FinMind API | 台股數據補強（免費） |
| 非結構化新聞 | MoneyDJ 爬蟲 | 自動定時抓取 |
| 非結構化重訊 | 公開資訊觀測站爬蟲 | 自動定時抓取 |
| 手動上傳 | PDF | 法說會逐字稿、券商研究報告 |

---

## 模組職責

| 模組 | 職責 |
|------|------|
| `data/fetcher.py` | yfinance + FinMind 結構化財報抓取 |
| `data/crawler.py` | 公開資訊觀測站 + MoneyDJ 爬蟲，存入 PostgreSQL |
| `data/ingestor.py` | PDF 解析 → 文字切塊 → embedding → 存 pgvector |
| `data/pg_repo.py` | PostgreSQL CRUD，含 pgvector 相似度查詢 |
| `ai/fundamental.py` | RAG 查詢 → LLM → `FundamentalReport` |
| `app/runner.py` | 平行呼叫回測 + 基本面，合併 `CombinedReport`（修改） |
| `app/streamlit_app.py` | 新增基本面 Tab + PDF 上傳元件（修改） |

---

## 資料庫設計

PostgreSQL + pgvector（需 pg 15+，`CREATE EXTENSION vector`）。

```sql
-- 文件來源紀錄
CREATE TABLE documents (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20),
    source      VARCHAR(50),   -- 'moneydj' | 'mops' | 'pdf_upload' | 'finmind'
    title       TEXT,
    url         TEXT,
    fetched_at  TIMESTAMP DEFAULT NOW()
);

-- 文字切塊 + 向量
CREATE TABLE document_chunks (
    id           SERIAL PRIMARY KEY,
    document_id  INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    content      TEXT,
    embedding    vector(1536),   -- 維度依 embedding provider 調整（OpenAI: 1536, Claude: 1024）
    created_at   TIMESTAMP DEFAULT NOW()
);

-- pgvector IVFFlat 索引（cosine 相似度）
CREATE INDEX ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

RAG 查詢範例：
```sql
SELECT content, document_id
FROM document_chunks
WHERE document_id IN (
    SELECT id FROM documents WHERE symbol = $1
)
ORDER BY embedding <=> $2
LIMIT 5;
```

---

## 資料結構

```python
@dataclass
class CardSection:
    title: str           # 面向名稱（7 大清單之一）
    bullets: list[str]   # 2-3 個重點條列
    data_source: str     # '財報數據' | '新聞' | '模型推估'

@dataclass
class FundamentalReport:
    symbol: str
    sections: list[CardSection]   # 7 張卡片
    final_verdict: Literal["建議操作", "觀望", "避開"]
    verdict_reason: str           # 1-2 句理由

@dataclass
class CombinedReport:
    symbol: str
    backtest_result: BacktestResult     # 現有
    fundamental: FundamentalReport      # 新增
    overall_verdict: str                # 合併建議
```

---

## 7 大清單對應資料來源

| 面向 | 主要資料來源 | 備援 |
|------|------------|------|
| 1. 商業模式與護城河 | yfinance longBusinessSummary, sector | 模型推估 |
| 2. 營收結構與成長動能 | totalRevenue, grossMargins, revenueGrowth | FinMind |
| 3. 終端市場與產業天花板 | RAG（新聞/法說會） | 模型推估 |
| 4. 投資論述與催化劑 | RAG（新聞）+ 52WeekHigh/Low | 模型推估 |
| 5. 同業財報 PK 與估值 | yfinance P/E, P/B + RAG | 模型推估 |
| 6. 資本配置與營收品質 | freeCashflow, dividendYield, payoutRatio | FinMind |
| 7. 管理層展望與下檔風險 | RAG（法說會 PDF） | 模型推估 |

---

## 觸發時機

回測與基本面分析**平行執行**：
- `runner.run_backtest()` 和 `StockAnalyst.analyze()` 同時啟動
- 兩者完成後合併為 `CombinedReport`
- Streamlit 顯示時以 Tab 區分：「回測結果」/ 「基本面分析」/ 「綜合建議」

---

## 技術選型

| 用途 | 選擇 | 理由 |
|------|------|------|
| 向量資料庫 | pgvector（PostgreSQL 擴充） | 統一單一 DB，個人工具規模夠用 |
| 主資料庫 | PostgreSQL | 現有選型延伸 |
| 結構化財報 | yfinance + FinMind | 免費，台股/美股皆支援 |
| Embedding 模型 | 沿用現有 LLM provider | 避免多套 SDK |
| PDF 解析 | pdfplumber 或 PyMuPDF | 輕量，無需 OCR |

---

## 測試策略

沿用現有 TDD 節奏：
- `tests/test_fetcher.py` — fixture CSV mock yfinance 回應
- `tests/test_crawler.py` — mock HTTP，驗證解析邏輯
- `tests/test_ingestor.py` — mock embedding，驗證切塊與存入
- `tests/test_pg_repo.py` — 測試用 in-memory 或 test DB
- `tests/test_fundamental.py` — mock RAG + mock LLM，驗證 `FundamentalReport` 結構

---

## 不在本次範圍

- 定時排程爬蟲（cron job）
- 多使用者隔離
- 雲端部署
- 即時報價 / 自動下單
