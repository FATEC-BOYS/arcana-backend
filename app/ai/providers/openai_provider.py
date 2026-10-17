from openai import OpenAI

from app.core.config import get_settings


class ProviderUnavailable(RuntimeError):
    pass


class OpenAIProvider:
    def __init__(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise ProviderUnavailable("llm_not_configured")
        self.client = OpenAI(
            api_key=settings.openai_api_key.get_secret_value(), timeout=30, max_retries=0
        )
        self.model = settings.llm_model
        self.input_tokens = self.output_tokens = self.calls = 0

    def structured(self, *, system: str, payload: str, schema):
        result = self.client.chat.completions.parse(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": payload}],
            response_format=schema,
            max_completion_tokens=1800,
        )
        self.calls += 1
        if result.usage:
            self.input_tokens += result.usage.prompt_tokens
            self.output_tokens += result.usage.completion_tokens
        content = result.choices[0].message.parsed
        if content is None:
            raise ProviderUnavailable("model_refused_or_incomplete")
        return content

    def embed(self, text: str) -> list[float]:
        result = self.client.embeddings.create(
            model=get_settings().embedding_model, input=text, dimensions=1536
        )
        if result.usage:
            self.input_tokens += result.usage.total_tokens
        self.calls += 1
        return result.data[0].embedding
