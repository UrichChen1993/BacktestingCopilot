# Next.js Frontend + FastAPI — Design Spec

**Date**: 2026-06-20  
**Status**: Approved

## Overview

Replace Streamlit UI with a React/Next.js frontend backed by a FastAPI HTTP layer. Streamlit is retained as a prototype/reference during transition. The Python business logic layer (`runner.py`, all domain modules) is untouched.

## Approach

Parallel UI strategy: Streamlit stays runnable, Next.js is built alongside it. Features migrate incrementally. Low risk — either UI can be used at any point.

## Repository Layout

```
BacktestingCopilot/
├── src/backtesting_copilot/
│   └── app/
│       ├── runner.py            # unchanged — all business logic lives here
│       ├── streamlit_app.py     # retained as prototype/reference
│       └── api/                 # new FastAPI layer
│           ├── __init__.py
│           ├── main.py          # FastAPI app, CORS config
│           └── routers/
│               ├── backtest.py
│               ├── optimize.py
│               └── advisor.py
│
└── frontend/                    # new Next.js project
    ├── package.json
    ├── .env.local               # NEXT_PUBLIC_API_URL=http://localhost:8000
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx         # backtest page
        │   └── optimize/
        │       └── page.tsx     # optimizer page
        ├── components/
        │   ├── BacktestForm.tsx
        │   ├── BacktestResult.tsx
        │   ├── OptimizerForm.tsx
        │   └── OptimizerResult.tsx
        └── lib/
            └── api.ts           # all fetch calls centralised here
```

## FastAPI Layer

**Start command**: `uvicorn backtesting_copilot.app.api.main:app --port 8000`

**CORS**: allow origin `http://localhost:3000` (Next.js dev).

### Endpoints

#### `POST /api/backtest`

Request body:
```json
{
  "symbol": "2330.TW",
  "strategy_type": "grid" | "value_averaging",
  "total_capital": 100000,
  "start_date": "2026-04-01",
  "end_date": "2026-05-31",
  "market_filter_enabled": true,
  "llm_provider": "offline" | "claude" | "openai" | "gemini" | "ollama",
  "grid_params": { "price_lower": 100, "price_upper": 112, "grid_num": 6 },
  "va_params": { "total_periods": 4, "period_interval_days": 14 }
}
```

Response:
```json
{
  "total_return": 0.05,
  "mdd": -0.03,
  "win_rate": 0.8,
  "trade_count": 12,
  "final_value": 105000,
  "realized_profit": 3000,
  "unrealized_profit": 2000,
  "market_filter_count": 2,
  "equity_curve": [["2026-04-01", 100000], ["2026-04-02", 100200]],
  "risk_level": "LOW",
  "paper_trading_ready": true,
  "summary": "...",
  "suggestions": ["..."],
  "narrative": "...",
  "trades_csv": "...",
  "report_md": "..."
}
```

#### `POST /api/optimize`

Request body:
```json
{
  "symbol": "2330.TW",
  "strategy_type": "grid",
  "total_capital": 100000,
  "start_date": "2026-04-01",
  "end_date": "2026-05-31",
  "max_rounds": 3,
  "llm_provider": "offline",
  "search_space": {
    "price_lower": [90, 95, 100],
    "price_upper": [110, 115, 120],
    "grid_num": [4, 6, 8]
  }
}
```

Response:
```json
{
  "best_params": { "price_lower": 95, "price_upper": 115, "grid_num": 6 },
  "best_score": 0.823,
  "stopped_reason": "convergence",
  "all_rounds": [
    {
      "round_num": 0,
      "params": {},
      "score": 0.823,
      "total_return": 0.05,
      "mdd": -0.03,
      "win_rate": 0.8,
      "trade_count": 12
    }
  ]
}
```

#### `GET /api/advisor`

Query params: `symbol`, `start_date`, `end_date`, `total_capital`, `llm_provider`

Response:
```json
{
  "recommended_strategy": "grid",
  "confidence_level": "HIGH",
  "reason": ["..."],
  "suggested_parameters": {},
  "risk_notes": ["..."],
  "narrative": "..."
}
```

### Error Handling

All errors return `{ "detail": "...", "error_code": "..." }`.

| Situation | HTTP Code |
|-----------|-----------|
| `DataUnavailableError` — cannot fetch market data | 422 |
| `ValidationError` — parameter validation failed | 400 |
| LLM provider not configured / unknown provider | 503 |
| LLM call failed (timeout, rate limit, network) | 502 |
| Unexpected exception | 500 |

## Next.js Frontend

**Stack**: Next.js 15 (App Router) + TypeScript + Ant Design 5 + `@ant-design/charts`

**Environment variable**: `NEXT_PUBLIC_API_URL=http://localhost:8000` — the only value to change for Docker/prod.

**Start command**: `npm run dev` (port 3000)

### Pages

| Route | Description |
|-------|-------------|
| `/` | Backtest: form inputs → submit → metrics, equity curve chart, trades table, AI analysis panel, CSV/MD download |
| `/optimize` | Optimizer: search space config → submit → ranked results table, best params JSON |

### State Management

`useState` + `useReducer` per page. No Redux — scope does not require it.

### API Client (`src/lib/api.ts`)

All `fetch` calls centralised here. On error, reads `error_code` and surfaces an Ant Design `notification.error()` with a human-readable message per code.

### Charts

`@ant-design/charts` `Line` component for equity curve. Optimizer results rendered in Ant Design `Table` with sortable columns.

## Local Development

```bash
# Terminal 1 — Python API
cd BacktestingCopilot
uvicorn backtesting_copilot.app.api.main:app --reload --port 8000

# Terminal 2 — Next.js
cd frontend
npm run dev   # http://localhost:3000

# Optional — Streamlit still works
streamlit run src/backtesting_copilot/app/streamlit_app.py
```

## Future: SSE Upgrade Path

When replacing sync with Server-Sent Events:
1. Change `POST /api/backtest` and `POST /api/optimize` to stream `text/event-stream`
2. Replace `fetch` in `api.ts` with `EventSource`
3. Frontend shows live progress without any structural changes to components

## Future: Docker

Single `docker-compose.yml` with two services (`api`, `frontend`). `NEXT_PUBLIC_API_URL` changes to the internal Docker network address. No other changes required.
