# Next.js + FastAPI Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI HTTP layer over `runner.py` and a Next.js/Ant Design frontend, replacing Streamlit as the primary UI while keeping Streamlit runnable as a reference.

**Architecture:** FastAPI wraps the existing `runner.py` functions with three endpoints (`/api/backtest`, `/api/optimize`, `/api/advisor`). Next.js (App Router) calls these endpoints and renders results using Ant Design 5 components. The two processes run independently on ports 8000 and 3000.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pydantic v2, Next.js 15, TypeScript, Ant Design 5, `@ant-design/charts`

---

## Phase 1: FastAPI Backend

### File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/backtesting_copilot/app/api/__init__.py` | package marker |
| Create | `src/backtesting_copilot/app/api/main.py` | FastAPI app, CORS, router registration |
| Create | `src/backtesting_copilot/app/api/schemas.py` | Pydantic request/response models |
| Create | `src/backtesting_copilot/app/api/errors.py` | exception → HTTP status mapping |
| Create | `src/backtesting_copilot/app/api/routers/backtest.py` | POST /api/backtest |
| Create | `src/backtesting_copilot/app/api/routers/optimize.py` | POST /api/optimize |
| Create | `src/backtesting_copilot/app/api/routers/advisor.py` | GET /api/advisor |
| Create | `src/backtesting_copilot/app/api/routers/__init__.py` | package marker |
| Create | `tests/test_api_backtest.py` | integration tests for /api/backtest |
| Create | `tests/test_api_optimize.py` | integration tests for /api/optimize |
| Create | `tests/test_api_advisor.py` | integration tests for /api/advisor |
| Modify | `pyproject.toml` | add fastapi, uvicorn, httpx to dependencies |

---

### Task 1: Add FastAPI dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Open `pyproject.toml` and add to the `[project] dependencies` list:

```toml
[project]
dependencies = [
    # ... existing deps ...
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",        # for TestClient in tests
]
```

- [ ] **Step 2: Install**

```bash
pip install -e ".[ai,dev]"
```

Expected: installs fastapi, uvicorn, httpx without errors.

- [ ] **Step 3: Verify FastAPI importable**

```bash
python -c "import fastapi; print(fastapi.__version__)"
```

Expected: prints version like `0.115.x`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(api): add fastapi uvicorn httpx dependencies"
```

---

### Task 2: Pydantic schemas

**Files:**
- Create: `src/backtesting_copilot/app/api/__init__.py`
- Create: `src/backtesting_copilot/app/api/routers/__init__.py`
- Create: `src/backtesting_copilot/app/api/schemas.py`

- [ ] **Step 1: Create package markers**

Create `src/backtesting_copilot/app/api/__init__.py` — empty file.
Create `src/backtesting_copilot/app/api/routers/__init__.py` — empty file.

- [ ] **Step 2: Write failing test for schema validation**

Create `tests/test_api_schemas.py`:

```python
import pytest
from backtesting_copilot.app.api.schemas import BacktestRequest, OptimizeRequest, AdvisorRequest


def test_backtest_request_grid_valid():
    req = BacktestRequest(
        symbol="2330.TW",
        strategy_type="grid",
        total_capital=100000,
        start_date="2026-04-01",
        end_date="2026-05-31",
        market_filter_enabled=True,
        llm_provider="offline",
        grid_params={"price_lower": 100.0, "price_upper": 112.0, "grid_num": 6},
    )
    assert req.strategy_type == "grid"
    assert req.grid_params["grid_num"] == 6


def test_backtest_request_va_valid():
    req = BacktestRequest(
        symbol="2330.TW",
        strategy_type="value_averaging",
        total_capital=100000,
        start_date="2026-04-01",
        end_date="2026-05-31",
        market_filter_enabled=False,
        llm_provider="offline",
        va_params={"total_periods": 4, "period_interval_days": 14},
    )
    assert req.va_params["total_periods"] == 4


def test_optimize_request_valid():
    req = OptimizeRequest(
        symbol="2330.TW",
        strategy_type="grid",
        total_capital=100000,
        start_date="2026-04-01",
        end_date="2026-05-31",
        max_rounds=3,
        llm_provider="offline",
        search_space={"price_lower": [90.0, 95.0], "price_upper": [110.0], "grid_num": [6]},
    )
    assert req.max_rounds == 3


def test_advisor_request_valid():
    req = AdvisorRequest(
        symbol="2330.TW",
        start_date="2026-04-01",
        end_date="2026-05-31",
        total_capital=100000,
        llm_provider="offline",
    )
    assert req.symbol == "2330.TW"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_api_schemas.py -v
```

Expected: `ImportError` — schemas module not found.

- [ ] **Step 4: Write schemas.py**

Create `src/backtesting_copilot/app/api/schemas.py`:

```python
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class GridParamsInput(BaseModel):
    price_lower: float
    price_upper: float
    grid_num: int


class VAParamsInput(BaseModel):
    total_periods: int
    period_interval_days: int


class BacktestRequest(BaseModel):
    symbol: str
    strategy_type: str  # "grid" | "value_averaging"
    total_capital: float
    start_date: str     # ISO date string, e.g. "2026-04-01"
    end_date: str
    market_filter_enabled: bool = True
    llm_provider: str = "offline"
    grid_params: dict[str, Any] | None = None
    va_params: dict[str, Any] | None = None


class EquityPoint(BaseModel):
    date: str
    value: float


class TradeRow(BaseModel):
    day: str
    side: str
    price: float
    quantity: float
    amount: float
    fee: float
    tax: float
    reason: str


class BacktestResponse(BaseModel):
    total_return: float
    mdd: float
    win_rate: float
    trade_count: int
    final_value: float
    realized_profit: float
    unrealized_profit: float
    market_filter_count: int
    warnings: list[str]
    equity_curve: list[EquityPoint]
    risk_level: str
    paper_trading_ready: bool
    summary: str
    suggestions: list[str]
    narrative: str
    trades: list[TradeRow]
    trades_csv: str
    report_md: str


class OptimizeRequest(BaseModel):
    symbol: str
    strategy_type: str
    total_capital: float
    start_date: str
    end_date: str
    max_rounds: int = 3
    llm_provider: str = "offline"
    search_space: dict[str, list[Any]]


class RoundResult(BaseModel):
    round_num: int
    params: dict[str, Any]
    score: float
    total_return: float
    mdd: float
    win_rate: float
    trade_count: int


class OptimizeResponse(BaseModel):
    best_params: dict[str, Any]
    best_score: float
    stopped_reason: str
    all_rounds: list[RoundResult]


class AdvisorRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    total_capital: float
    llm_provider: str = "offline"


class AdvisorResponse(BaseModel):
    recommended_strategy: str
    confidence_level: str
    reason: list[str]
    suggested_parameters: dict[str, Any]
    risk_notes: list[str]
    narrative: str
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_api_schemas.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/backtesting_copilot/app/api/ tests/test_api_schemas.py
git commit -m "feat(api): add pydantic request/response schemas"
```

---

### Task 3: Error handler

**Files:**
- Create: `src/backtesting_copilot/app/api/errors.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_api_errors.py`:

```python
from backtesting_copilot.app.api.errors import classify_exception
from backtesting_copilot.data.provider import DataUnavailableError
from backtesting_copilot.validator.parameter_validator import ValidationError


def test_data_unavailable_is_422():
    code, detail = classify_exception(DataUnavailableError("no data"))
    assert code == 422
    assert "DATA_UNAVAILABLE" in detail["error_code"]


def test_validation_error_is_400():
    code, detail = classify_exception(ValidationError("bad param"))
    assert code == 400
    assert "VALIDATION_ERROR" in detail["error_code"]


def test_unknown_exception_is_500():
    code, detail = classify_exception(RuntimeError("boom"))
    assert code == 500
    assert "INTERNAL_ERROR" in detail["error_code"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_errors.py -v
```

Expected: `ImportError` — errors module not found.

- [ ] **Step 3: Check what ValidationError exists in validator module**

```bash
python -c "from backtesting_copilot.validator.parameter_validator import ValidationResult; print('ok')"
```

Note: the validator uses `ValidationResult` (dataclass), not a raised exception. Parameter validation failures are returned as `ValidationResult.valid == False`, not raised. The `ValidationError` for HTTP 400 needs to be a custom exception we raise in the router when `ValidationResult.valid` is False.

- [ ] **Step 4: Write errors.py**

Create `src/backtesting_copilot/app/api/errors.py`:

```python
from __future__ import annotations
from backtesting_copilot.data.provider import DataUnavailableError


class APIValidationError(Exception):
    """Raised by routers when parameter validation fails."""
    def __init__(self, message: str) -> None:
        super().__init__(message)


def classify_exception(exc: Exception) -> tuple[int, dict]:
    if isinstance(exc, DataUnavailableError):
        return 422, {"detail": str(exc), "error_code": "DATA_UNAVAILABLE"}
    if isinstance(exc, APIValidationError):
        return 400, {"detail": str(exc), "error_code": "VALIDATION_ERROR"}
    if isinstance(exc, (ValueError, TypeError)):
        return 400, {"detail": str(exc), "error_code": "VALIDATION_ERROR"}
    return 500, {"detail": str(exc), "error_code": "INTERNAL_ERROR"}
```

- [ ] **Step 5: Update test to use APIValidationError**

Update `tests/test_api_errors.py`:

```python
from backtesting_copilot.app.api.errors import classify_exception, APIValidationError
from backtesting_copilot.data.provider import DataUnavailableError


def test_data_unavailable_is_422():
    code, detail = classify_exception(DataUnavailableError("no data"))
    assert code == 422
    assert detail["error_code"] == "DATA_UNAVAILABLE"


def test_validation_error_is_400():
    code, detail = classify_exception(APIValidationError("bad param"))
    assert code == 400
    assert detail["error_code"] == "VALIDATION_ERROR"


def test_unknown_exception_is_500():
    code, detail = classify_exception(RuntimeError("boom"))
    assert code == 500
    assert detail["error_code"] == "INTERNAL_ERROR"
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_api_errors.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/backtesting_copilot/app/api/errors.py tests/test_api_errors.py
git commit -m "feat(api): add error classification helper"
```

---

### Task 4: /api/backtest router

**Files:**
- Create: `src/backtesting_copilot/app/api/routers/backtest.py`
- Create: `tests/test_api_backtest.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/test_api_backtest.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backtesting_copilot.app.api.main import app
    return TestClient(app)


def test_backtest_grid_offline(client):
    resp = client.post("/api/backtest", json={
        "symbol": "2330.TW",
        "strategy_type": "grid",
        "total_capital": 100000,
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "market_filter_enabled": False,
        "llm_provider": "offline",
        "grid_params": {"price_lower": 500.0, "price_upper": 600.0, "grid_num": 6},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "total_return" in data
    assert "mdd" in data
    assert "equity_curve" in data
    assert "trades_csv" in data
    assert "risk_level" in data


def test_backtest_invalid_strategy_type(client):
    resp = client.post("/api/backtest", json={
        "symbol": "2330.TW",
        "strategy_type": "unknown_strategy",
        "total_capital": 100000,
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "market_filter_enabled": False,
        "llm_provider": "offline",
    })
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_backtest.py -v
```

Expected: `ImportError` — main module not found.

- [ ] **Step 3: Write the backtest router**

Create `src/backtesting_copilot/app/api/routers/backtest.py`:

```python
from __future__ import annotations
from datetime import date
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.api.errors import APIValidationError, classify_exception
from backtesting_copilot.app.api.schemas import (
    BacktestRequest, BacktestResponse, EquityPoint, TradeRow,
)
from backtesting_copilot.app.runner import build_engine, run_backtest
from backtesting_copilot.config import get_settings
from backtesting_copilot.models import (
    GridParams, StrategyConfig, StrategyType, ValueAveragingParams,
)
from backtesting_copilot.validator import validate_config

router = APIRouter()


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _build_config(req: BacktestRequest) -> StrategyConfig:
    try:
        stype = StrategyType(req.strategy_type)
    except ValueError:
        raise APIValidationError(f"Unknown strategy_type: {req.strategy_type!r}")

    common = dict(
        symbol=req.symbol,
        total_capital=req.total_capital,
        start_date=_parse_date(req.start_date),
        end_date=_parse_date(req.end_date),
        market_filter_enabled=req.market_filter_enabled,
    )
    if stype == StrategyType.GRID:
        if not req.grid_params:
            raise APIValidationError("grid_params required for grid strategy")
        gp = req.grid_params
        return StrategyConfig(
            strategy_type=stype,
            grid=GridParams(
                price_lower=gp["price_lower"],
                price_upper=gp["price_upper"],
                grid_num=int(gp["grid_num"]),
            ),
            **common,
        )
    if not req.va_params:
        raise APIValidationError("va_params required for value_averaging strategy")
    vp = req.va_params
    return StrategyConfig(
        strategy_type=stype,
        value_averaging=ValueAveragingParams(
            total_periods=int(vp["total_periods"]),
            period_interval_days=int(vp["period_interval_days"]),
        ),
        **common,
    )


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest_endpoint(req: BacktestRequest):
    try:
        config = _build_config(req)
        validation = validate_config(config)
        if not validation.valid:
            raise APIValidationError("; ".join(validation.errors))

        settings = get_settings()
        engine = build_engine(settings)
        provider = get_provider(settings)
        out = run_backtest(config, engine, llm_provider=provider)
        r = out.result

        return BacktestResponse(
            total_return=r.total_return,
            mdd=r.mdd,
            win_rate=r.win_rate,
            trade_count=r.trade_count,
            final_value=r.final_value,
            realized_profit=r.realized_profit,
            unrealized_profit=r.unrealized_profit,
            market_filter_count=r.market_filter_count,
            warnings=r.warnings,
            equity_curve=[
                EquityPoint(date=str(d), value=v) for d, v in r.equity_curve
            ],
            risk_level=out.report.risk_level,
            paper_trading_ready=out.report.paper_trading_ready,
            summary=out.report.summary,
            suggestions=out.report.suggestions,
            narrative=out.report.narrative or "",
            trades=[
                TradeRow(
                    day=str(t.day),
                    side=t.side.value,
                    price=t.price,
                    quantity=t.quantity,
                    amount=t.amount,
                    fee=t.fee,
                    tax=t.tax,
                    reason=t.reason or "",
                )
                for t in r.trades
            ],
            trades_csv=out.trades_csv,
            report_md=out.report_md,
        )
    except Exception as exc:
        status, body = classify_exception(exc)
        return JSONResponse(status_code=status, content=body)
```

- [ ] **Step 4: Write main.py**

Create `src/backtesting_copilot/app/api/main.py`:

```python
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backtesting_copilot.app.api.routers import backtest, optimize, advisor

app = FastAPI(title="BacktestingCopilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backtest.router, prefix="/api")
app.include_router(optimize.router, prefix="/api")
app.include_router(advisor.router, prefix="/api")
```

- [ ] **Step 5: Run test (network call to yfinance will happen — test uses real dates with known data)**

```bash
pytest tests/test_api_backtest.py -v
```

Expected: both tests PASS. (The valid test fetches real data from yfinance; the invalid one returns 400 immediately.)

If yfinance is unavailable (no internet), the valid test will return 422 — that's also acceptable. Add a skip marker if needed:

```python
import os
@pytest.mark.skipif(os.getenv("CI") == "true", reason="no network in CI")
def test_backtest_grid_offline(client):
    ...
```

- [ ] **Step 6: Commit**

```bash
git add src/backtesting_copilot/app/api/ tests/test_api_backtest.py
git commit -m "feat(api): add POST /api/backtest endpoint"
```

---

### Task 5: /api/optimize router

**Files:**
- Create: `src/backtesting_copilot/app/api/routers/optimize.py`
- Create: `tests/test_api_optimize.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_api_optimize.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backtesting_copilot.app.api.main import app
    return TestClient(app)


def test_optimize_grid_offline(client):
    resp = client.post("/api/optimize", json={
        "symbol": "2330.TW",
        "strategy_type": "grid",
        "total_capital": 100000,
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "max_rounds": 0,
        "llm_provider": "offline",
        "search_space": {
            "price_lower": [500.0, 510.0],
            "price_upper": [580.0, 600.0],
            "grid_num": [6],
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "best_params" in data
    assert "best_score" in data
    assert "all_rounds" in data
    assert isinstance(data["all_rounds"], list)


def test_optimize_invalid_strategy(client):
    resp = client.post("/api/optimize", json={
        "symbol": "2330.TW",
        "strategy_type": "bogus",
        "total_capital": 100000,
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "max_rounds": 0,
        "llm_provider": "offline",
        "search_space": {"price_lower": [500.0], "price_upper": [600.0], "grid_num": [6]},
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_optimize.py -v
```

Expected: router not found → 404 or import error.

- [ ] **Step 3: Write optimize router**

Create `src/backtesting_copilot/app/api/routers/optimize.py`:

```python
from __future__ import annotations
from datetime import date
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backtesting_copilot.ai.optimizer import OptimizationConfig
from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.api.errors import APIValidationError, classify_exception
from backtesting_copilot.app.api.schemas import OptimizeRequest, OptimizeResponse, RoundResult
from backtesting_copilot.app.runner import build_engine, run_optimization
from backtesting_copilot.config import get_settings
from backtesting_copilot.models import StrategyType

router = APIRouter()


@router.post("/optimize", response_model=OptimizeResponse)
def run_optimize_endpoint(req: OptimizeRequest):
    try:
        try:
            stype = StrategyType(req.strategy_type)
        except ValueError:
            raise APIValidationError(f"Unknown strategy_type: {req.strategy_type!r}")

        settings = get_settings()
        engine = build_engine(settings)
        provider = get_provider(settings)

        opt_cfg = OptimizationConfig(
            strategy_type=stype,
            symbol=req.symbol,
            start_date=date.fromisoformat(req.start_date),
            end_date=date.fromisoformat(req.end_date),
            total_capital=req.total_capital,
            search_space=req.search_space,
            max_rounds=req.max_rounds,
        )
        result = run_optimization(opt_cfg, engine, provider)

        return OptimizeResponse(
            best_params=result.best_params,
            best_score=result.best_score,
            stopped_reason=result.stopped_reason,
            all_rounds=[
                RoundResult(
                    round_num=r.round_num,
                    params=r.params,
                    score=r.score,
                    total_return=r.result.total_return,
                    mdd=r.result.mdd,
                    win_rate=r.result.win_rate,
                    trade_count=r.result.trade_count,
                )
                for r in result.all_rounds
            ],
        )
    except Exception as exc:
        status, body = classify_exception(exc)
        return JSONResponse(status_code=status, content=body)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_api_optimize.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backtesting_copilot/app/api/routers/optimize.py tests/test_api_optimize.py
git commit -m "feat(api): add POST /api/optimize endpoint"
```

---

### Task 6: /api/advisor router

**Files:**
- Create: `src/backtesting_copilot/app/api/routers/advisor.py`
- Create: `tests/test_api_advisor.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_api_advisor.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backtesting_copilot.app.api.main import app
    return TestClient(app)


def test_advisor_offline(client):
    resp = client.get("/api/advisor", params={
        "symbol": "2330.TW",
        "start_date": "2024-01-02",
        "end_date": "2024-03-29",
        "total_capital": 100000,
        "llm_provider": "offline",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended_strategy" in data
    assert "confidence_level" in data
    assert isinstance(data["reason"], list)
    assert "suggested_parameters" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_advisor.py -v
```

Expected: 404 (router not registered yet).

- [ ] **Step 3: Write advisor router**

Create `src/backtesting_copilot/app/api/routers/advisor.py`:

```python
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backtesting_copilot.ai.advisor import recommend_strategy
from backtesting_copilot.ai.provider import get_provider
from backtesting_copilot.app.api.errors import classify_exception
from backtesting_copilot.app.api.schemas import AdvisorResponse
from backtesting_copilot.app.runner import build_provider
from backtesting_copilot.config import get_settings
from backtesting_copilot.features.price_features import PriceFeatures

router = APIRouter()


@router.get("/advisor", response_model=AdvisorResponse)
def get_advisor(
    symbol: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    total_capital: float = Query(...),
    llm_provider: str = Query("offline"),
):
    try:
        settings = get_settings()
        data_provider = build_provider(settings)
        bars = data_provider.get_ohlcv(
            symbol,
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
        )

        if not bars or len(bars) < 5:
            # not enough data — return offline fallback with minimal features
            features = PriceFeatures(
                high_40=0, low_40=0, range_pct_40=0,
                ma_60=None, ma_60_slope=None,
            )
        else:
            closes = [b.close for b in bars]
            highs = [b.high for b in bars]
            lows = [b.low for b in bars]
            high_40 = max(highs[-40:]) if len(highs) >= 40 else max(highs)
            low_40 = min(lows[-40:]) if len(lows) >= 40 else min(lows)
            ma_60 = sum(closes[-60:]) / len(closes[-60:]) if len(closes) >= 60 else None
            slope = None
            if ma_60 and len(closes) >= 61:
                prev_ma = sum(closes[-61:-1]) / 60
                slope = ma_60 - prev_ma
            features = PriceFeatures(
                high_40=high_40,
                low_40=low_40,
                range_pct_40=(high_40 - low_40) / low_40 if low_40 else 0,
                ma_60=ma_60,
                ma_60_slope=slope,
            )

        llm = get_provider(settings)
        rec = recommend_strategy(features, total_capital, provider=llm)

        return AdvisorResponse(
            recommended_strategy=rec.recommended_strategy.value,
            confidence_level=rec.confidence_level,
            reason=rec.reason,
            suggested_parameters=rec.suggested_parameters,
            risk_notes=rec.risk_notes,
            narrative=rec.narrative or "",
        )
    except Exception as exc:
        status, body = classify_exception(exc)
        return JSONResponse(status_code=status, content=body)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_api_advisor.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite to make sure nothing broken**

```bash
pytest -q
```

Expected: all tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add src/backtesting_copilot/app/api/routers/advisor.py tests/test_api_advisor.py
git commit -m "feat(api): add GET /api/advisor endpoint"
```

---

### Task 7: Smoke-test the running API

**Files:** none (manual verification)

- [ ] **Step 1: Start the API server**

```bash
uvicorn backtesting_copilot.app.api.main:app --reload --port 8000
```

Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 2: Open API docs**

Navigate to `http://localhost:8000/docs` in a browser.

Expected: Swagger UI showing three endpoints: `POST /api/backtest`, `POST /api/optimize`, `GET /api/advisor`.

- [ ] **Step 3: Test /api/advisor via curl**

In a new terminal:

```bash
curl "http://localhost:8000/api/advisor?symbol=2330.TW&start_date=2024-01-02&end_date=2024-03-29&total_capital=100000&llm_provider=offline"
```

Expected: JSON with `recommended_strategy`, `confidence_level`, `reason` fields.

- [ ] **Step 4: Stop server (Ctrl+C)**

---

## Phase 2: Next.js Frontend

### File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `frontend/` | Next.js project root |
| Create | `frontend/.env.local` | API URL config |
| Create | `frontend/src/lib/api.ts` | all fetch calls, error handling |
| Create | `frontend/src/lib/types.ts` | TypeScript types matching API schemas |
| Create | `frontend/src/components/BacktestForm.tsx` | strategy inputs form |
| Create | `frontend/src/components/BacktestResult.tsx` | metrics, chart, trades, AI panel |
| Create | `frontend/src/components/OptimizerForm.tsx` | search space inputs |
| Create | `frontend/src/components/OptimizerResult.tsx` | ranked results table + best params |
| Create | `frontend/src/app/layout.tsx` | root layout with AntD provider |
| Create | `frontend/src/app/page.tsx` | backtest page |
| Create | `frontend/src/app/optimize/page.tsx` | optimizer page |

---

### Task 8: Scaffold Next.js project

**Files:**
- Create: `frontend/` (entire project)

- [ ] **Step 1: Scaffold with create-next-app**

From the repo root (`BacktestingCopilot/`):

```bash
npx create-next-app@latest frontend --typescript --app --no-tailwind --no-src-dir --import-alias "@/*" --yes
```

Wait for completion.

- [ ] **Step 2: Move into frontend and install Ant Design + charts**

```bash
cd frontend
npm install antd @ant-design/icons @ant-design/charts
```

- [ ] **Step 3: Create .env.local**

Create `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 4: Verify dev server starts**

```bash
npm run dev
```

Expected: `ready - started server on 0.0.0.0:3000`

Open `http://localhost:3000` — should see default Next.js welcome page.

Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
cd ..   # back to repo root
git add frontend/
git commit -m "feat(frontend): scaffold Next.js project with AntD"
```

---

### Task 9: TypeScript types and API client

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create types.ts**

Create `frontend/src/lib/types.ts`:

```typescript
export interface GridParams {
  price_lower: number;
  price_upper: number;
  grid_num: number;
}

export interface VAParams {
  total_periods: number;
  period_interval_days: number;
}

export interface BacktestRequest {
  symbol: string;
  strategy_type: "grid" | "value_averaging";
  total_capital: number;
  start_date: string;
  end_date: string;
  market_filter_enabled: boolean;
  llm_provider: string;
  grid_params?: GridParams;
  va_params?: VAParams;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface TradeRow {
  day: string;
  side: string;
  price: number;
  quantity: number;
  amount: number;
  fee: number;
  tax: number;
  reason: string;
}

export interface BacktestResponse {
  total_return: number;
  mdd: number;
  win_rate: number;
  trade_count: number;
  final_value: number;
  realized_profit: number;
  unrealized_profit: number;
  market_filter_count: number;
  warnings: string[];
  equity_curve: EquityPoint[];
  risk_level: string;
  paper_trading_ready: boolean;
  summary: string;
  suggestions: string[];
  narrative: string;
  trades: TradeRow[];
  trades_csv: string;
  report_md: string;
}

export interface OptimizeRequest {
  symbol: string;
  strategy_type: "grid" | "value_averaging";
  total_capital: number;
  start_date: string;
  end_date: string;
  max_rounds: number;
  llm_provider: string;
  search_space: Record<string, number[]>;
}

export interface RoundResult {
  round_num: number;
  params: Record<string, unknown>;
  score: number;
  total_return: number;
  mdd: number;
  win_rate: number;
  trade_count: number;
}

export interface OptimizeResponse {
  best_params: Record<string, unknown>;
  best_score: number;
  stopped_reason: string;
  all_rounds: RoundResult[];
}

export interface AdvisorResponse {
  recommended_strategy: string;
  confidence_level: string;
  reason: string[];
  suggested_parameters: Record<string, unknown>;
  risk_notes: string[];
  narrative: string;
}

export interface ApiError {
  detail: string;
  error_code: string;
}
```

- [ ] **Step 2: Create api.ts**

Create `frontend/src/lib/api.ts`:

```typescript
import type {
  BacktestRequest, BacktestResponse,
  OptimizeRequest, OptimizeResponse,
  AdvisorResponse, ApiError,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      detail: "Unknown error",
      error_code: "UNKNOWN",
    }));
    throw err;
  }
  return res.json() as Promise<T>;
}

export async function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  const res = await fetch(`${BASE}/api/backtest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<BacktestResponse>(res);
}

export async function runOptimize(req: OptimizeRequest): Promise<OptimizeResponse> {
  const res = await fetch(`${BASE}/api/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<OptimizeResponse>(res);
}

export async function getAdvisor(params: {
  symbol: string;
  start_date: string;
  end_date: string;
  total_capital: number;
  llm_provider: string;
}): Promise<AdvisorResponse> {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();
  const res = await fetch(`${BASE}/api/advisor?${qs}`);
  return handleResponse<AdvisorResponse>(res);
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/lib/
git commit -m "feat(frontend): add TypeScript types and API client"
```

---

### Task 10: Root layout with Ant Design

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Rewrite layout.tsx**

Replace the contents of `frontend/src/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";

export const metadata: Metadata = {
  title: "AI 雙軌回測 Copilot",
  description: "策略由數學規則執行 · 風控由硬規則把關 · AI 負責分析",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body>
        <AntdRegistry>{children}</AntdRegistry>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Install AntD Next.js registry package**

```bash
cd frontend
npm install @ant-design/nextjs-registry
```

- [ ] **Step 3: Verify build compiles**

```bash
npm run build
```

Expected: build succeeds (may show warnings, no errors).

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat(frontend): configure AntD with Next.js registry"
```

---

### Task 11: BacktestForm component

**Files:**
- Create: `frontend/src/components/BacktestForm.tsx`

- [ ] **Step 1: Create BacktestForm.tsx**

Create `frontend/src/components/BacktestForm.tsx`:

```tsx
"use client";
import { useState } from "react";
import {
  Form, Input, InputNumber, Select, DatePicker, Switch, Button, Divider,
} from "antd";
import type { BacktestRequest, GridParams, VAParams } from "@/lib/types";
import dayjs from "dayjs";

interface Props {
  onSubmit: (req: BacktestRequest) => void;
  loading: boolean;
}

export default function BacktestForm({ onSubmit, loading }: Props) {
  const [strategyType, setStrategyType] = useState<"grid" | "value_averaging">("grid");
  const [form] = Form.useForm();

  function handleFinish(values: Record<string, unknown>) {
    const req: BacktestRequest = {
      symbol: values.symbol as string,
      strategy_type: strategyType,
      total_capital: values.total_capital as number,
      start_date: dayjs(values.start_date as string).format("YYYY-MM-DD"),
      end_date: dayjs(values.end_date as string).format("YYYY-MM-DD"),
      market_filter_enabled: values.market_filter_enabled as boolean,
      llm_provider: values.llm_provider as string,
    };
    if (strategyType === "grid") {
      req.grid_params = {
        price_lower: values.price_lower as number,
        price_upper: values.price_upper as number,
        grid_num: values.grid_num as number,
      } as GridParams;
    } else {
      req.va_params = {
        total_periods: values.total_periods as number,
        period_interval_days: values.period_interval_days as number,
      } as VAParams;
    }
    onSubmit(req);
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        symbol: "2330.TW",
        total_capital: 100000,
        market_filter_enabled: true,
        llm_provider: "offline",
        price_lower: 500,
        price_upper: 600,
        grid_num: 6,
        total_periods: 4,
        period_interval_days: 14,
      }}
    >
      <Form.Item label="標的" name="symbol" rules={[{ required: true }]}>
        <Input />
      </Form.Item>

      <Form.Item label="策略">
        <Select
          value={strategyType}
          onChange={(v) => setStrategyType(v)}
          options={[
            { label: "網格交易", value: "grid" },
            { label: "價值平均", value: "value_averaging" },
          ]}
        />
      </Form.Item>

      <Form.Item label="總資金" name="total_capital" rules={[{ required: true }]}>
        <InputNumber min={1000} step={1000} style={{ width: "100%" }} />
      </Form.Item>

      <Form.Item label="開始日期" name="start_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>

      <Form.Item label="結束日期" name="end_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>

      <Form.Item label="LLM Provider" name="llm_provider">
        <Select
          options={[
            { label: "離線（規則）", value: "offline" },
            { label: "Claude", value: "claude" },
            { label: "OpenAI", value: "openai" },
            { label: "Gemini", value: "gemini" },
            { label: "Ollama", value: "ollama" },
          ]}
        />
      </Form.Item>

      <Form.Item label="啟用大盤 60MA 濾網" name="market_filter_enabled" valuePropName="checked">
        <Switch />
      </Form.Item>

      <Divider />

      {strategyType === "grid" ? (
        <>
          <Form.Item label="區間下限" name="price_lower" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="區間上限" name="price_upper" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="網格層數" name="grid_num" rules={[{ required: true }]}>
            <InputNumber min={1} max={12} style={{ width: "100%" }} />
          </Form.Item>
        </>
      ) : (
        <>
          <Form.Item label="總扣款次數" name="total_periods" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="每期間隔天數" name="period_interval_days" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
        </>
      )}

      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          驗證並回測
        </Button>
      </Form.Item>
    </Form>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/components/BacktestForm.tsx
git commit -m "feat(frontend): add BacktestForm component"
```

---

### Task 12: BacktestResult component

**Files:**
- Create: `frontend/src/components/BacktestResult.tsx`

- [ ] **Step 1: Create BacktestResult.tsx**

Create `frontend/src/components/BacktestResult.tsx`:

```tsx
"use client";
import {
  Row, Col, Statistic, Alert, Table, Tag, Typography, Card, Divider, Button,
} from "antd";
import { Line } from "@ant-design/charts";
import type { BacktestResponse, TradeRow } from "@/lib/types";

const { Title, Paragraph } = Typography;

interface Props {
  data: BacktestResponse;
}

export default function BacktestResult({ data }: Props) {
  const equityData = data.equity_curve.map((p) => ({
    date: p.date,
    value: p.value,
  }));

  const lineConfig = {
    data: equityData,
    xField: "date",
    yField: "value",
    smooth: true,
    height: 260,
  };

  const tradeColumns = [
    { title: "日期", dataIndex: "day", key: "day" },
    {
      title: "方向",
      dataIndex: "side",
      key: "side",
      render: (v: string) => (
        <Tag color={v === "BUY" ? "green" : "red"}>{v}</Tag>
      ),
    },
    { title: "價格", dataIndex: "price", key: "price" },
    { title: "數量", dataIndex: "quantity", key: "quantity" },
    { title: "金額", dataIndex: "amount", key: "amount" },
    { title: "備註", dataIndex: "reason", key: "reason" },
  ];

  function downloadFile(content: string, filename: string, mime: string) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const riskColor =
    data.risk_level === "LOW" ? "success" :
    data.risk_level === "MEDIUM" ? "warning" : "error";

  return (
    <div style={{ marginTop: 24 }}>
      {data.warnings.map((w, i) => (
        <Alert key={i} type="warning" message={w} style={{ marginBottom: 8 }} />
      ))}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="總報酬率" value={(data.total_return * 100).toFixed(2)} suffix="%" /></Col>
        <Col span={6}><Statistic title="最大回撤 MDD" value={(data.mdd * 100).toFixed(2)} suffix="%" /></Col>
        <Col span={6}><Statistic title="勝率" value={(data.win_rate * 100).toFixed(0)} suffix="%" /></Col>
        <Col span={6}><Statistic title="交易次數" value={data.trade_count} /></Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="期末總資產" value={data.final_value.toFixed(0)} /></Col>
        <Col span={6}><Statistic title="已實現損益" value={data.realized_profit.toFixed(0)} /></Col>
        <Col span={6}><Statistic title="未實現損益" value={data.unrealized_profit.toFixed(0)} /></Col>
        <Col span={6}><Statistic title="風控觸發次數" value={data.market_filter_count} /></Col>
      </Row>

      {equityData.length > 0 && (
        <Card title="權益曲線" style={{ marginBottom: 16 }}>
          <Line {...lineConfig} />
        </Card>
      )}

      <Card title="AI 回測分析" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Alert type={riskColor} message={`風險等級：${data.risk_level}`} />
          </Col>
          <Col span={6}>
            <Alert
              type={data.paper_trading_ready ? "success" : "warning"}
              message={data.paper_trading_ready ? "✅ Paper Trading 就緒" : "⚠️ 尚未就緒"}
            />
          </Col>
        </Row>
        <Paragraph style={{ marginTop: 12 }}>{data.summary}</Paragraph>
        <ul>
          {data.suggestions.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
        {data.narrative && (
          <Alert type="info" message={`🤖 AI 敘述：${data.narrative}`} style={{ marginTop: 8 }} />
        )}
      </Card>

      <Divider />

      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col>
          <Button onClick={() => downloadFile(data.trades_csv, "trades.csv", "text/csv")}>
            下載交易明細 CSV
          </Button>
        </Col>
        <Col>
          <Button onClick={() => downloadFile(data.report_md, "report.md", "text/markdown")}>
            下載回測報告 Markdown
          </Button>
        </Col>
      </Row>

      <Title level={5}>交易明細</Title>
      <Table
        dataSource={data.trades}
        columns={tradeColumns}
        rowKey={(r: TradeRow) => `${r.day}-${r.side}-${r.price}`}
        size="small"
        pagination={{ pageSize: 20 }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/components/BacktestResult.tsx
git commit -m "feat(frontend): add BacktestResult component"
```

---

### Task 13: Backtest page (/)

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Replace page.tsx**

Replace `frontend/src/app/page.tsx` with:

```tsx
"use client";
import { useState } from "react";
import { Layout, Typography, notification, Spin, Row, Col } from "antd";
import BacktestForm from "@/components/BacktestForm";
import BacktestResult from "@/components/BacktestResult";
import { runBacktest } from "@/lib/api";
import type { BacktestRequest, BacktestResponse, ApiError } from "@/lib/types";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

export default function BacktestPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [api, contextHolder] = notification.useNotification();

  async function handleSubmit(req: BacktestRequest) {
    setLoading(true);
    setResult(null);
    try {
      const data = await runBacktest(req);
      setResult(data);
    } catch (err) {
      const e = err as ApiError;
      api.error({
        message: "回測失敗",
        description: `[${e.error_code}] ${e.detail}`,
        duration: 6,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {contextHolder}
      <Header style={{ background: "#001529", padding: "0 24px" }}>
        <Title level={4} style={{ color: "#fff", margin: "16px 0 8px" }}>
          AI 雙軌回測 Copilot
        </Title>
        <Text style={{ color: "#aaa", fontSize: 12 }}>
          策略由數學規則執行 · 風控由硬規則把關 · AI 負責分析 · 使用者保留最終決策權
        </Text>
      </Header>
      <Content style={{ padding: 24 }}>
        <Row gutter={24}>
          <Col xs={24} md={8}>
            <BacktestForm onSubmit={handleSubmit} loading={loading} />
          </Col>
          <Col xs={24} md={16}>
            {loading && <Spin size="large" tip="回測進行中…" style={{ marginTop: 80, display: "block" }} />}
            {result && !loading && <BacktestResult data={result} />}
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/app/page.tsx
git commit -m "feat(frontend): add backtest page"
```

---

### Task 14: Optimizer page (/optimize)

**Files:**
- Create: `frontend/src/components/OptimizerForm.tsx`
- Create: `frontend/src/components/OptimizerResult.tsx`
- Create: `frontend/src/app/optimize/page.tsx`

- [ ] **Step 1: Create OptimizerForm.tsx**

Create `frontend/src/components/OptimizerForm.tsx`:

```tsx
"use client";
import { Form, Input, InputNumber, Select, DatePicker, Button, Space } from "antd";
import type { OptimizeRequest } from "@/lib/types";
import dayjs from "dayjs";

interface Props {
  onSubmit: (req: OptimizeRequest) => void;
  loading: boolean;
}

export default function OptimizerForm({ onSubmit, loading }: Props) {
  const [form] = Form.useForm();

  function handleFinish(values: Record<string, unknown>) {
    const req: OptimizeRequest = {
      symbol: values.symbol as string,
      strategy_type: values.strategy_type as "grid" | "value_averaging",
      total_capital: values.total_capital as number,
      start_date: dayjs(values.start_date as string).format("YYYY-MM-DD"),
      end_date: dayjs(values.end_date as string).format("YYYY-MM-DD"),
      max_rounds: values.max_rounds as number,
      llm_provider: values.llm_provider as string,
      search_space: {
        price_lower: (values.price_lower as string).split(",").map(Number),
        price_upper: (values.price_upper as string).split(",").map(Number),
        grid_num: (values.grid_num as string).split(",").map(Number),
      },
    };
    onSubmit(req);
  }

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        symbol: "2330.TW",
        strategy_type: "grid",
        total_capital: 100000,
        max_rounds: 3,
        llm_provider: "offline",
        price_lower: "500,510,520",
        price_upper: "580,590,600",
        grid_num: "4,6,8",
      }}
    >
      <Form.Item label="標的" name="symbol" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="策略" name="strategy_type">
        <Select options={[
          { label: "網格交易", value: "grid" },
          { label: "價值平均", value: "value_averaging" },
        ]} />
      </Form.Item>
      <Form.Item label="總資金" name="total_capital">
        <InputNumber min={1000} step={1000} style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="開始日期" name="start_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="結束日期" name="end_date" rules={[{ required: true }]}>
        <DatePicker style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="LLM Provider" name="llm_provider">
        <Select options={[
          { label: "離線（規則）", value: "offline" },
          { label: "Claude", value: "claude" },
          { label: "OpenAI", value: "openai" },
        ]} />
      </Form.Item>
      <Form.Item label="LLM 精細輪數" name="max_rounds">
        <InputNumber min={0} max={10} style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="price_lower 候選（逗號分隔）" name="price_lower">
        <Input />
      </Form.Item>
      <Form.Item label="price_upper 候選（逗號分隔）" name="price_upper">
        <Input />
      </Form.Item>
      <Form.Item label="grid_num 候選（逗號分隔）" name="grid_num">
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          啟動優化
        </Button>
      </Form.Item>
    </Form>
  );
}
```

- [ ] **Step 2: Create OptimizerResult.tsx**

Create `frontend/src/components/OptimizerResult.tsx`:

```tsx
"use client";
import { Table, Card, Statistic, Row, Col, Tag, Typography } from "antd";
import type { OptimizeResponse, RoundResult } from "@/lib/types";

const { Title } = Typography;

interface Props {
  data: OptimizeResponse;
}

export default function OptimizerResult({ data }: Props) {
  const columns = [
    {
      title: "來源",
      dataIndex: "round_num",
      key: "source",
      render: (v: number) =>
        v === 0 ? <Tag color="blue">Phase 1 全搜尋</Tag> : <Tag color="purple">Phase 2 LLM 輪次 {v}</Tag>,
    },
    { title: "Score", dataIndex: "score", key: "score", render: (v: number) => v.toFixed(4), sorter: (a: RoundResult, b: RoundResult) => b.score - a.score },
    { title: "報酬率", dataIndex: "total_return", key: "total_return", render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { title: "MDD", dataIndex: "mdd", key: "mdd", render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { title: "勝率", dataIndex: "win_rate", key: "win_rate", render: (v: number) => `${(v * 100).toFixed(0)}%` },
    { title: "交易數", dataIndex: "trade_count", key: "trade_count" },
  ];

  return (
    <div style={{ marginTop: 24 }}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic title="最佳 Score" value={data.best_score.toFixed(4)} />
        </Col>
        <Col span={8}>
          <Statistic title="停止原因" value={data.stopped_reason} />
        </Col>
      </Row>

      <Card title="最佳參數" style={{ marginBottom: 16 }}>
        <pre style={{ margin: 0 }}>{JSON.stringify(data.best_params, null, 2)}</pre>
      </Card>

      <Title level={5}>所有輪次結果</Title>
      <Table
        dataSource={data.all_rounds}
        columns={columns}
        rowKey={(r: RoundResult) => `${r.round_num}-${r.score}`}
        size="small"
        pagination={false}
      />
    </div>
  );
}
```

- [ ] **Step 3: Create optimize page**

Create `frontend/src/app/optimize/page.tsx`:

```tsx
"use client";
import { useState } from "react";
import { Layout, Typography, notification, Spin, Row, Col } from "antd";
import OptimizerForm from "@/components/OptimizerForm";
import OptimizerResult from "@/components/OptimizerResult";
import { runOptimize } from "@/lib/api";
import type { OptimizeRequest, OptimizeResponse, ApiError } from "@/lib/types";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

export default function OptimizePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [api, contextHolder] = notification.useNotification();

  async function handleSubmit(req: OptimizeRequest) {
    setLoading(true);
    setResult(null);
    try {
      const data = await runOptimize(req);
      setResult(data);
    } catch (err) {
      const e = err as ApiError;
      api.error({
        message: "優化失敗",
        description: `[${e.error_code}] ${e.detail}`,
        duration: 6,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {contextHolder}
      <Header style={{ background: "#001529", padding: "0 24px" }}>
        <Title level={4} style={{ color: "#fff", margin: "16px 0 8px" }}>
          AI 雙軌回測 Copilot — 自動優化
        </Title>
        <Text style={{ color: "#aaa", fontSize: 12 }}>
          Phase 1 全搜尋 + Phase 2 LLM 精細搜尋
        </Text>
      </Header>
      <Content style={{ padding: 24 }}>
        <Row gutter={24}>
          <Col xs={24} md={8}>
            <OptimizerForm onSubmit={handleSubmit} loading={loading} />
          </Col>
          <Col xs={24} md={16}>
            {loading && <Spin size="large" tip="優化進行中…" style={{ marginTop: 80, display: "block" }} />}
            {result && !loading && <OptimizerResult data={result} />}
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/
git commit -m "feat(frontend): add optimizer page and components"
```

---

### Task 15: End-to-end smoke test (manual)

**Files:** none (manual verification)

- [ ] **Step 1: Start FastAPI**

Terminal 1:
```bash
uvicorn backtesting_copilot.app.api.main:app --reload --port 8000
```

- [ ] **Step 2: Start Next.js**

Terminal 2:
```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Open http://localhost:3000**

Expected: Backtest page loads with a form on the left.

- [ ] **Step 4: Submit a backtest**

Fill in:
- 標的: `2330.TW`
- 策略: 網格交易
- 開始日期: `2024-01-02`, 結束日期: `2024-03-29`
- 區間下限: `500`, 區間上限: `600`, 網格層數: `6`

Click 驗證並回測.

Expected: metrics appear on the right, equity curve chart renders, trades table shows rows (or "本次無成交" if no signals fired).

- [ ] **Step 5: Navigate to /optimize**

Open `http://localhost:3000/optimize`.

Expected: Optimizer form loads. Submit with default values. Results table appears.

- [ ] **Step 6: Verify error handling**

Set 標的 to an invalid ticker `XXXXINVALID` and submit.

Expected: Ant Design `notification.error` toast appears with error message. App does not crash.

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "feat: Next.js + FastAPI frontend — Phase 1 complete (sync mode)"
```
