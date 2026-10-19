"""Privacy-safe, bounded and reproducible metadata spans for LangGraph.

No prompts, questions, answers, free-form exceptions, source text or user IDs.
Only fixed stage labels and numeric counters from the provider are persisted.
"""

from contextlib import contextmanager
from time import perf_counter

STAGES = frozenset({"retrieval", "interpret", "review", "reject"})
METRICS = ("calls", "input_tokens", "output_tokens", "embedding_tokens")


def _snapshot(provider):
    if provider is None:
        return {}
    return {
        metric: max(0, int(getattr(provider, metric, 0) or 0))
        for metric in METRICS
    }


class RunTrace:
    def __init__(self):
        self.steps: list[dict] = []
        self.review_outcomes: list[bool] = []

    @contextmanager
    def step(self, name: str, *, provider=None):
        if name not in STAGES:
            raise ValueError("unknown_telemetry_stage")
        start_metrics = _snapshot(provider)
        started = perf_counter()
        status = "ok"
        try:
            yield
        except BaseException:
            status = "error"
            raise
        finally:
            entry = {
                "stage": name,
                "status": status,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }
            for metric, before in start_metrics.items():
                entry[metric] = max(0, _snapshot(provider)[metric] - before)
            self.steps.append(entry)

    def reviewed(self, approved: bool):
        if not isinstance(approved, bool):
            raise ValueError("invalid_review_decision")
        self.review_outcomes.append(approved)

    def as_dict(self) -> dict:
        return {
            "steps": list(self.steps),
            "review_outcomes": list(self.review_outcomes),
            "interpret_attempts": sum(x["stage"] == "interpret" for x in self.steps),
            "review_rejections": self.review_outcomes.count(False),
        }
