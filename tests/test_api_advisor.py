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
