import json

from app.ai.schemas.state import Interpretation, Review


class FakeProvider:
    model = "test-double"
    embedding_model = "text-embedding-3-small"

    def __init__(self):
        self.calls = self.input_tokens = self.output_tokens = self.embedding_tokens = 0

    def structured(self, *, system, payload, schema):
        self.calls += 1
        data = json.loads(payload)
        if schema == Review:
            return Review(approved=True, feedback="")
        return Interpretation(
            summary="Uma interpretação simbólica sustentada pelo acervo de teste.",
            reflections=["Como isso se relaciona ao seu contexto?"],
            source_ids=[data["sources"][0]["source_id"]],
            fact_ids=[data["fact_ids"][0]],
        )


def create_reading(client, auth, key="release-reading-1", **extra):
    result = client.post(
        "/api/v1/readings",
        headers={**auth, "Idempotency-Key": key},
        json={"question": "Como refletir sobre meu trabalho?", **extra},
    )
    assert result.status_code == 202, result.text
    return result.json()
