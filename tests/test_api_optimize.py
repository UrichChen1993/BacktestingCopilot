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
