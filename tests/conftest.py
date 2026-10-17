import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine
from app.main import create_app
from app.rag.seed import seed_knowledge


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Set TEST_DATABASE_URL to a disposable PostgreSQL database for dialect integration checks.
    monkeypatch.setenv(
        "DATABASE_URL", os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    )
    monkeypatch.setenv("AUTH_ATTEMPT_LIMIT", "100")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    get_engine.cache_clear()
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_knowledge(db)
    with TestClient(create_app()) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def auth(client):
    result = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "name": "Ale", "password": "a-long-test-password"},
    )
    assert result.status_code == 201, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}
