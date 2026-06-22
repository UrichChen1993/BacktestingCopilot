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
