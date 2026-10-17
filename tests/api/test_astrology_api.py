from app.ai.schemas.state import Interpretation, Review
from app.jobs.worker import process_one


def test_natal_chart_and_interpretation(client, auth):
    result = client.post(
        "/api/v1/astrology/charts",
        headers=auth,
        json={
            "birth_date": "1990-07-15",
            "birth_time": "10:30",
            "latitude": -23.55,
            "longitude": -46.63,
            "timezone": "America/Sao_Paulo",
        },
    )
    assert result.status_code == 201, result.text
    chart = result.json()
    assert chart["data"]["planets"]["sun"]["sign"] == "Can"
    assert client.get("/api/v1/astrology/charts", headers=auth).json()[0]["id"] == chart["id"]
    created = client.post(
        "/api/v1/readings",
        headers={**auth, "Idempotency-Key": "astro-reading-1"},
        json={
            "kind": "astrology",
            "chart_id": chart["id"],
            "question": "Como olhar meu momento profissional?",
        },
    )
    assert created.status_code == 202, created.text
    assert created.json()["chart_id"] == chart["id"]

    class Provider:
        model = "test"
        input_tokens = output_tokens = calls = 0

        def structured(self, *, system, payload, schema):
            import json

            self.calls += 1
            d = json.loads(payload)
            assert "birth_date" not in d["facts"]
            assert "utc" not in d["facts"]
            assert "chart_id" not in d["facts"]
            if schema == Review:
                return Review(approved=True, feedback="")
            return Interpretation(
                summary="Uma reflexão simbólica sobre o mapa calculado.",
                reflections=["O que te inspira?"],
                source_ids=[d["sources"][0]["source_id"]],
                fact_ids=["sun"],
            )

    assert process_one(Provider)
    assert (
        client.get("/api/v1/readings/" + created.json()["id"], headers=auth).json()["status"]
        == "completed"
    )
