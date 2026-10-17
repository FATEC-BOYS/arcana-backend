import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_explicit_rate_limit_secret():
    with pytest.raises(ValidationError, match="RATE_LIMIT_SECRET"):
        Settings(
            _env_file=None, environment="production", rate_limit_secret="local-development-only"
        )
    assert (
        Settings(_env_file=None, environment="production", rate_limit_secret="a" * 40).environment
        == "production"
    )


def test_wildcard_cors_is_rejected():
    with pytest.raises(ValidationError, match="explicit frontend origins"):
        Settings(_env_file=None, cors_origins=["*"])
