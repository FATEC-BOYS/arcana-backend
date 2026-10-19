import pytest

from app.ai.evaluation import assess_answer
from app.ai.observability import RunTrace
from app.ai.orchestration.graph import InvalidGeneration, build_reading_graph
from app.ai.schemas.state import Interpretation, Review
from tests.support import FakeProvider


def payload():
    return {
        "question": "Como refletir sobre o trabalho?",
        "facts": {"cards": [{"card_id": "major-01", "name": "O Mago"}]},
        "fact_ids": ["major-01"],
        "sources": [{"source_id": "source-1", "text": "Fonte sintética."}],
        "history": [],
    }


def test_agent_graph_records_success_without_private_content():
    trace = RunTrace()
    state = build_reading_graph(FakeProvider(), trace=trace).invoke(
        {"payload": payload(), "corrections": -1}
    )
    assert state["review"]["approved"]
    observation = trace.as_dict()
    assert [s["stage"] for s in observation["steps"]] == ["interpret", "review"]
    assert observation["interpret_attempts"] == 1
    assert observation["review_rejections"] == 0
    assert "Fonte sintética" not in str(observation)
    assert "Como refletir" not in str(observation)


def test_reviewer_can_request_a_single_revision():
    class NeedsCorrection(FakeProvider):
        def __init__(self):
            super().__init__()
            self.review_count = 0

        def structured(self, *, system, payload, schema):
            if schema is Review:
                self.review_count += 1
                return Review(approved=self.review_count == 2, feedback="Reescreva.")
            return super().structured(system=system, payload=payload, schema=schema)

    trace = RunTrace()
    provider = NeedsCorrection()
    state = build_reading_graph(provider, trace=trace).invoke(
        {"payload": payload(), "corrections": -1}
    )
    assert state["corrections"] == 1
    assert provider.review_count == 2
    assert trace.as_dict()["review_rejections"] == 1
    assert [x["stage"] for x in trace.steps] == [
        "interpret", "review", "interpret", "review"
    ]


def test_final_rejection_never_publishes_an_answer():
    class RejectAll(FakeProvider):
        def structured(self, *, system, payload, schema):
            if schema is Review:
                return Review(approved=False, feedback="Reprovado.")
            return super().structured(system=system, payload=payload, schema=schema)

    trace = RunTrace()
    with pytest.raises(InvalidGeneration, match="review_rejected"):
        build_reading_graph(RejectAll(), trace=trace).invoke(
            {"payload": payload(), "corrections": -1}
        )
    assert trace.as_dict()["review_rejections"] == 2
    assert trace.steps[-1]["stage"] == "reject"
    assert trace.steps[-1]["status"] == "error"


def test_hallucinated_citations_are_rejected_and_recorded():
    class InvalidSource(FakeProvider):
        def structured(self, *, system, payload, schema):
            if schema is Interpretation:
                return Interpretation(
                    summary="Uma leitura simbólica de teste com conteúdo privado.",
                    reflections=["Uma reflexão."],
                    source_ids=["unretrieved-source"],
                    fact_ids=["major-01"],
                )
            return super().structured(system=system, payload=payload, schema=schema)

    trace = RunTrace()
    with pytest.raises(InvalidGeneration, match="invalid_citations"):
        build_reading_graph(InvalidSource(), trace=trace).invoke(
            {"payload": payload(), "corrections": -1}
        )
    assert trace.steps[0]["status"] == "error"
    assert "conteúdo privado" not in str(trace.as_dict())


def test_quality_rubric_flags_injection_and_unsupported_facts():
    answer = {
        "summary": "O Mago convida a refletir sobre possibilidades.",
        "reflections": ["Que caminhos fazem sentido?"],
        "source_ids": ["source-1"],
        "fact_ids": ["major-01"],
    }
    options = {
        "allowed_source_ids": {"source-1"},
        "allowed_fact_ids": {"major-01"},
        "card_names": ["O Mago"],
        "forbidden_phrases": ["Destino Absoluto"],
        "reviewer_approved": True,
    }
    assert assess_answer(answer, **options)["passed"]
    assert not assess_answer(
        {**answer, "summary": "O Mago é o Destino Absoluto."}, **options
    )["checks"]["injection_phrase_absent"]
    assert not assess_answer(
        {**answer, "fact_ids": ["invented"]}, **options
    )["checks"]["facts_grounded"]
    assert not assess_answer(
        {**answer, "summary": "É garantido que você ganhará."}, **options
    )["checks"]["no_categorical_prediction"]


def test_trace_rejects_arbitrary_stage_labels():
    with pytest.raises(ValueError, match="unknown_telemetry_stage"):
        with RunTrace().step("user_question"):
            pass
