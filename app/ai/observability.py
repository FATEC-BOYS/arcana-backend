"""Privacy-safe per-node telemetry for the reading graph.

Only fixed stage names, timings and boolean review decisions are collected.
No prompts, source text, user questions, generated answers or reviewer feedback.
"""

from contextlib import contextmanager
from time import perf_counter

STAGES = frozenset({"retrieval", "interpret", "review", "reject"})


class RunTrace:
    def __init__(self):
        self.steps: list[dict] = []
        self.review_outcomes: list[bool] = []

    @contextmanager
    def step(self, name: str):
        if name not in STAGES:
            raise ValueError("unknown_telemetry_stage")
        started = perf_counter()
        status = "ok"
        try:
            yield
        except BaseException:
            status = "error"
            raise
        finally:
            self.steps.append(
                {
                    "stage": name,
                    "status": status,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                }
            )

    def reviewed(self, approved: bool):
        self.review_outcomes.append(bool(approved))

    def as_dict(self) -> dict:
        return {
            "steps": list(self.steps),
            "review_outcomes": list(self.review_outcomes),
            "interpret_attempts": sum(x["stage"] == "interpret" for x in self.steps),
            "review_rejections": self.review_outcomes.count(False),
        }
