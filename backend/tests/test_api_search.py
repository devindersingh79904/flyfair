import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.constants import Headers, ResponseStatus

@pytest.fixture
def client():
    """Fixture that initializes client with context manager to trigger lifespan events."""
    with TestClient(app) as c:
        yield c

def test_api_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == ResponseStatus.SUCCESS.value
    assert json_data["message"] == "Service is healthy"
    assert "timestamp" in json_data
    assert "correlationId" in json_data

def test_api_search_success(client):
    headers = {Headers.CORRELATION_ID.value: "custom-corr-123"}
    response = client.get("/api/v1/airports/search?q=Londn&limit=5", headers=headers)
    assert response.status_code == 200
    
    # Verify Echoed Header
    assert response.headers.get(Headers.CORRELATION_ID.value) == "custom-corr-123"
    
    # Verify Response Envelope
    json_data = response.json()
    assert json_data["status"] == ResponseStatus.SUCCESS.value
    assert json_data["correlationId"] == "custom-corr-123"
    assert "timestamp" in json_data
    assert "data" in json_data
    assert "results" in json_data["data"]
    assert json_data["errors"] == []
    
    # Verify Metadata
    meta = json_data["meta"]
    assert meta["limit"] == 5
    assert "count" in meta
    assert meta["hasMore"] is False
    assert "latencyMs" in meta

def test_api_search_empty_query(client):
    # Empty query should fail query verification and return 422
    response = client.get("/api/v1/airports/search?q=%20%20")
    assert response.status_code == 422
    json_data = response.json()
    assert json_data["status"] == ResponseStatus.ERROR.value
    assert len(json_data["errors"]) > 0
    assert json_data["errors"][0]["field"] == "q"

def test_api_search_invalid_limit(client):
    # Limit exceeding bounds (25 > 20) triggers FastAPI schema validation (422)
    response = client.get("/api/v1/airports/search?q=London&limit=25")
    assert response.status_code == 422
    json_data = response.json()
    assert json_data["status"] == ResponseStatus.ERROR.value
    assert len(json_data["errors"]) > 0
    assert json_data["errors"][0]["field"] == "limit"
