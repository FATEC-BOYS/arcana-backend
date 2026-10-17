from openai import APIError, OpenAI
from pydantic import ValidationError

from app.core.config import get_settings


class ProviderUnavailable(RuntimeError):
    pass


class ProviderFailure(RuntimeError):
    def __init__(self, code: str, *, retryable: bool):
        super().__init__(code)
        self.retryable = retryable


def provider_error(exc: APIError) -> ProviderFailure:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return ProviderFailure("provider_auth_error", retryable=False)
    if status == 429:
        return ProviderFailure("provider_rate_limited", retryable=True)
    if status is None or status >= 500:
        return ProviderFailure("provider_temporarily_unavailable", retryable=True)
    return ProviderFailure("provider_invalid_request", retryable=False)


class OpenAIProvider:
    def __init__(self, client=None):
        settings = get_settings()
        if client is None and not settings.openai_api_key:
            raise ProviderUnavailable("llm_not_configured")
        self.client = client or OpenAI(
            api_key=settings.openai_api_key.get_secret_value(), timeout=30, max_retries=0
        )
        self.model, self.embedding_model = settings.llm_model, settings.embedding_model
        self.input_tokens = self.output_tokens = self.embedding_tokens = self.calls = 0

    def structured(self, *, system: str, payload: str, schema):
        if len(payload) > get_settings().max_context_chars:
            raise ProviderUnavailable("context_limit_exceeded")
        self.calls += 1
        try:
            result = self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": payload},
                ],
                response_format=schema,
                max_completion_tokens=1800,
            )
        except APIError as exc:
            raise provider_error(exc) from None
        except (ValidationError, ValueError):
            raise ProviderUnavailable("invalid_model_output") from None
        if result.usage:
            self.input_tokens += result.usage.prompt_tokens
            self.output_tokens += result.usage.completion_tokens
        content = result.choices[0].message.parsed
        if content is None:
            raise ProviderUnavailable("model_refused_or_incomplete")
        return content

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        try:
            result = self.client.embeddings.create(
                model=self.embedding_model, input=text, dimensions=1536
            )
        except APIError as exc:
            raise provider_error(exc) from None
        if result.usage:
            self.embedding_tokens += result.usage.total_tokens
        vector = result.data[0].embedding
        if len(vector) != 1536:
            raise ProviderUnavailable("embedding_dimension_mismatch")
        return vector
