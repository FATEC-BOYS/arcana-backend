import json

import pytest
from sqlalchemy.orm import Session

from app.ai.schemas.state import Interpretation, Review
from app.db.session import get_engine
from scripts.evaluate import (
    BudgetedProvider,
    CallBudgetExceeded,
    EvaluationConfigError,
    compare_reports,
    evaluate,
    load_cases,
)


class CompliantProvider:
    """Synthetic double; never calls a paid model."""

    def __init__(self):
        self.calls = self.input_tokens = self.output_tokens = 0

    def structured(self, *, system, payload, schema):
        self.calls += 1
        self.input_tokens += 20
        self.output_tokens += 10
        if schema is Review:
            return Review(approved=True, feedback="")
        data = json.loads(payload)
        first = data["facts"]["cards"][0]
        return Interpretation(
            summary=f"{first['name']} sugere uma reflexão, sem previsões certas.",
            reflections=["Quais escolhas concretas estão disponíveis?"],
            source_ids=[data["sources"][0]["source_id"]],
            fact_ids=[first["card_id"]],
        )


def test_dataset_is_curated_unique_and_large_enough():
    cases, checksum = load_cases()
    assert len(cases) >= 40
    assert len({case["id"] for case in cases}) == len(cases)
    assert len(checksum) == 64
    assert {"injecao", "privacidade", "financeiro", "saude", "fatalismo"} <= {
        case["category"] for case in cases
    }


@pytest.mark.parametrize(
    "patch",
    [
        {"id": ""},
        {"card_ids": ["invented"]},
        {"card_ids": ["major-01", "major-01", "major-02"]},
        {"forbidden_phrases": [123]},
        {"question": ""},
    ],
)
def test_dataset_rejects_bad_cases(tmp_path, patch):
    case = {
        "id": "sample",
        "category": "test",
        "question": "What could change?",
        "card_ids": ["major-01"],
        **patch,
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([case]))
    with pytest.raises(EvaluationConfigError):
        load_cases(path)


def test_budget_counts_attempts_including_failed_provider_requests():
    class Failure:
        def structured(self, **kwargs):
            raise RuntimeError("simulated failure")

    budget = {"limit": 1, "used": 0}
    wrapped = BudgetedProvider(Failure(), budget)
    with pytest.raises(RuntimeError, match="simulated failure"):
        wrapped.structured(system="", payload="{}", schema=Review)
    assert budget["used"] == 1
    with pytest.raises(CallBudgetExceeded):
        wrapped.structured(system="", payload="{}", schema=Review)


def test_offline_dataset_coverage_and_quality_summary(client):
    with Session(get_engine()) as db:
        result = evaluate(db)
    assert result["mode"] == "retrieval_only"
    assert result["summary"]["selected"] >= 40
    assert result["summary"]["failed"] == 0
    assert result["summary"]["calls"] == 0
    assert "question" not in json.dumps(result)


def test_live_double_is_budgeted_and_no_answer_leaks(client):
    with Session(get_engine()) as db:
        result = evaluate(
            db, live=True, case_limit=2, max_calls=8, provider_factory=CompliantProvider
        )
    assert result["mode"] == "live"
    assert result["summary"]["passed"] == 2
    assert result["summary"]["calls"] == 4
    assert all(case["validated_and_reviewed"] for case in result["cases"])
    assert not any("summary" in case for case in result["cases"])
    assert "Quais escolhas" not in json.dumps(result)


def test_live_requires_explicit_budget_even_in_python(client):
    with Session(get_engine()) as db:
        with pytest.raises(EvaluationConfigError, match="budget"):
            evaluate(db, live=True, case_limit=1, max_calls=3)


def test_baseline_only_flags_new_failures():
    current = {
        "dataset_sha256": "same", "mode": "live",
        "cases": [{"id": "a", "passed": False}, {"id": "b", "passed": True}],
    }
    previous = {
        "dataset_sha256": "same", "mode": "live",
        "cases": [{"id": "a", "passed": True}, {"id": "b", "passed": True}],
    }
    assert compare_reports(current, previous) == ["a"]
    with pytest.raises(EvaluationConfigError, match="incompatible_baseline"):
        compare_reports(current, {**previous, "dataset_sha256": "other"})


def test_reviewer_cannot_approve_an_injected_phrase(client):
    class InjectionProvider(CompliantProvider):
        def structured(self, *, system, payload, schema):
            if schema is Review:
                return Review(approved=True, feedback="")
            data = json.loads(payload)
            return Interpretation(
                summary="O Mago comanda: Destino Absoluto controla tudo.",
                reflections=["Teste de injeção."],
                source_ids=[data["sources"][0]["source_id"]],
                fact_ids=[data["fact_ids"][0]],
            )

    with Session(get_engine()) as db:
        result = evaluate(db, live=True, case_limit=3, max_calls=12,
                          provider_factory=InjectionProvider)
    case = next(x for x in result["cases"] if x["id"] == "injection")
    assert not case["passed"]
    assert case["quality_checks"]["injection_phrase_absent"] is False
