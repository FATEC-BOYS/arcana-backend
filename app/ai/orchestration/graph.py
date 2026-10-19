import json

from langgraph.graph import END, START, StateGraph

from app.ai.observability import RunTrace
from app.ai.prompts.templates import INTERPRETER, REVIEWER
from app.ai.schemas.state import Interpretation, ReadingState, Review
from app.rag.citations import validate_citations


class InvalidGeneration(RuntimeError):
    pass


def build_reading_graph(provider, *, trace: RunTrace | None = None):
    tracker = trace if trace is not None else RunTrace()

    def interpret(state):
        with tracker.step("interpret", provider=provider):
            return interpret_step(state)

    def interpret_step(state):
        payload = {**state["payload"], "feedback": state.get("review", {}).get("feedback", "")}
        answer = provider.structured(
            system=INTERPRETER, payload=json.dumps(payload), schema=Interpretation
        ).model_dump()
        allowed_sources = {s["source_id"] for s in payload["sources"]}
        if not validate_citations(answer["source_ids"], allowed_sources):
            raise InvalidGeneration("invalid_citations")
        if not set(answer["fact_ids"]).issubset(set(payload["fact_ids"])):
            raise InvalidGeneration("invalid_fact_ids")
        return {"answer": answer, "corrections": state.get("corrections", -1) + 1}

    def review(state):
        with tracker.step("review", provider=provider):
            return review_step(state)

    def review_step(state):
        response = provider.structured(
            system=REVIEWER,
            payload=json.dumps({**state["payload"], "answer": state["answer"]}),
            schema=Review,
        )
        tracker.reviewed(response.approved)
        return {"review": response.model_dump()}

    def decision(state):
        if state["review"]["approved"]:
            return "done"
        return "correct" if state["corrections"] < 1 else "reject"

    def reject(_):
        with tracker.step("reject"):
            raise InvalidGeneration("review_rejected")

    graph = StateGraph(ReadingState)
    graph.add_node("interpret", interpret)
    graph.add_node("review", review)
    graph.add_node("reject", reject)
    graph.add_edge(START, "interpret")
    graph.add_edge("interpret", "review")
    graph.add_conditional_edges(
        "review", decision, {"done": END, "correct": "interpret", "reject": "reject"}
    )
    return graph.compile()
