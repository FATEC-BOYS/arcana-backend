import json

import httpx
import pytest
from openai import OpenAI

from app.ai.providers.openai_provider import OpenAIProvider, ProviderFailure, ProviderUnavailable
from app.ai.schemas.state import Interpretation


def make_client(handler):
    return OpenAI(
        api_key="synthetic-test-key",
        base_url="https://model.test/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def response(content):
    return {
        "id": "test-completion",
        "object": "chat.completion",
        "created": 1,
        "model": "test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(content)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }


def test_sdk_structured_output_contract():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["strict"]
        assert body["max_completion_tokens"] == 1800
        return httpx.Response(
            200,
            json=response(
                {
                    "summary": "Uma reflexão simbólica de teste.",
                    "reflections": ["O que faz sentido?"],
                    "source_ids": ["source-1"],
                    "fact_ids": ["sun"],
                }
            ),
        )

    with make_client(handler) as client:
        provider = OpenAIProvider(client)
        result = provider.structured(system="Synthetic prompt", payload="{}", schema=Interpretation)
        assert result.fact_ids == ["sun"]
        assert provider.input_tokens == 20 and provider.output_tokens == 10 and provider.calls == 1


@pytest.mark.parametrize(
    "status,retryable,code",
    [
        (401, False, "provider_auth_error"),
        (429, True, "provider_rate_limited"),
        (503, True, "provider_temporarily_unavailable"),
        (400, False, "provider_invalid_request"),
    ],
)
def test_provider_errors_are_sanitized(status, retryable, code):
    def handler(request):
        return httpx.Response(
            status, json={"error": {"message": "private-upstream-detail", "type": "api_error"}}
        )

    with make_client(handler) as client:
        provider = OpenAIProvider(client)
        with pytest.raises(ProviderFailure) as result:
            provider.structured(system="test", payload="{}", schema=Interpretation)
        assert str(result.value) == code and result.value.retryable is retryable
        assert "private" not in str(result.value)
        assert provider.calls == 1


def test_embeddings_use_matching_dimension_and_separate_usage():
    def handler(request):
        body = json.loads(request.content)
        assert body["dimensions"] == 1536
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
                "model": "text-embedding-3-small",
                "usage": {"prompt_tokens": 4, "total_tokens": 4},
            },
        )

    with make_client(handler) as client:
        provider = OpenAIProvider(client)
        assert len(provider.embed("synthetic text")) == 1536
        assert provider.embedding_tokens == 4 and provider.input_tokens == 0


def test_malformed_output_never_becomes_a_reading():
    def handler(request):
        value = response({})
        value["choices"][0]["message"]["content"] = "not-json"
        return httpx.Response(200, json=value)

    with make_client(handler) as client:
        with pytest.raises(ProviderUnavailable, match="invalid_model_output"):
            OpenAIProvider(client).structured(system="test", payload="{}", schema=Interpretation)
