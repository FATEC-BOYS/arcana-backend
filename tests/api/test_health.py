from fastapi.testclient import TestClient
from app.main import create_app


def test_liveness_without_database_or_llm():
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/api/v1/spreads").status_code == 200
        assert client.get("/openapi.json").status_code == 200
