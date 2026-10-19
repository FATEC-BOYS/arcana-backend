"""Reproducible synthetic Arcana evaluation with explicit paid-call budgets.

Offline retrieval checks are the default. A live run requires both a case limit
and a hard call budget; reports never contain questions, answers or source text.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.evaluation import assess_answer
from app.ai.orchestration.graph import build_reading_graph
from app.ai.prompts.templates import PROMPT_VERSION
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import get_settings
from app.db.session import get_engine
from app.modules.cards.catalog import CARD_BY_ID
from app.rag.retrieval import search

DATASET = Path(__file__).resolve().parents[1] / "evaluations/datasets/tarot.json"
MAX_CASES = 1000


class EvaluationConfigError(ValueError):
    pass


class CallBudgetExceeded(RuntimeError):
    pass


class BudgetedProvider:
    """Guarantee the maximum number of paid chat calls, even on graph retries."""

    def __init__(self, provider, budget):
        self.provider = provider
        self.budget = budget

    def structured(self, *, system, payload, schema):
        if self.budget["used"] >= self.budget["limit"]:
            raise CallBudgetExceeded("call_budget_exceeded")
        self.budget["used"] += 1  # Count attempted requests (including failures).
        return self.provider.structured(system=system, payload=payload, schema=schema)


def load_cases(path=DATASET):
    raw = Path(path).read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise EvaluationConfigError("invalid_dataset_size")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationConfigError("invalid_case")
        case_id, category, question = (
            case.get("id"), case.get("category"), case.get("question")
        )
        ids = case.get("card_ids")
        forbidden = case.get("forbidden_phrases", [])
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise EvaluationConfigError("duplicate_or_missing_case_id")
        if not isinstance(category, str) or not category or len(category) > 60:
            raise EvaluationConfigError("invalid_case_category")
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise EvaluationConfigError("invalid_question")
        if (
            not isinstance(ids, list)
            or len(ids) not in (1, 3)
            or len(ids) != len(set(ids))
            or any(not isinstance(x, str) or x not in CARD_BY_ID for x in ids)
        ):
            raise EvaluationConfigError("invalid_card_ids")
        if (
            not isinstance(forbidden, list)
            or len(forbidden) > 10
            or any(not isinstance(x, str) or not x or len(x) > 120 for x in forbidden)
        ):
            raise EvaluationConfigError("invalid_forbidden_phrases")
        seen.add(case_id)
    return cases, hashlib.sha256(raw).hexdigest()


def compare_reports(current, baseline):
    """Exact matching synthetic scenarios; raw user content is never involved."""
    if (
        current["dataset_sha256"] != baseline.get("dataset_sha256")
        or current["mode"] != baseline.get("mode")
    ):
        raise EvaluationConfigError("incompatible_baseline")
    prior = {x["id"]: x for x in baseline.get("cases", [])}
    ids = {x["id"] for x in current["cases"]}
    if set(prior) != ids:
        raise EvaluationConfigError("incompatible_baseline_cases")
    return sorted(
        case["id"]
        for case in current["cases"]
        if prior[case["id"]]["passed"] and not case["passed"]
    )


def evaluate(
    db, *, live=False, case_limit=None, max_calls=None,
    provider_factory=OpenAIProvider, dataset=DATASET,
):
    cases, dataset_hash = load_cases(dataset)
    if case_limit is not None and not 1 <= case_limit <= len(cases):
        raise EvaluationConfigError("invalid_case_limit")
    if live and (
        case_limit is None or max_calls is None or max_calls < 4 * case_limit
    ):
        raise EvaluationConfigError("live_requires_four_calls_budget_per_selected_case")
    selected = cases[:case_limit] if case_limit is not None else cases
    budget = {"limit": max_calls or 0, "used": 0}
    results = []
    for case in selected:
        ids = case["card_ids"]
        sources = search(db, topic="tarot", tags=ids)
        coverage = all(any(id_ in item.source_id for item in sources) for id_ in ids)
        row = {
            "id": case["id"],
            "category": case["category"],
            "retrieval_coverage": coverage,
            "source_count": len(sources),
            "passed": coverage,
        }
        if live:
            # Avoid sending a case with missing evidence to the paid provider.
            if not coverage:
                row.update(passed=False, validated_and_reviewed=False, failure="missing_evidence")
            else:
                provider = provider_factory()
                guarded = BudgetedProvider(provider, budget)
                start_calls = budget["used"]
                try:
                    state = build_reading_graph(guarded).invoke(
                        {
                            "payload": {
                                "question": case["question"],
                                "facts": {
                                    "cards": [
                                        {"card_id": key, "name": CARD_BY_ID[key]["name"],
                                         "reversed": False}
                                        for key in ids
                                    ]
                                },
                                "fact_ids": ids,
                                "sources": [asdict(item) for item in sources],
                                "history": [],
                                "original_reading": None,
                            },
                            "corrections": -1,
                        }
                    )
                    assessment = assess_answer(
                        state["answer"],
                        allowed_source_ids={source.source_id for source in sources},
                        allowed_fact_ids=set(ids),
                        card_names=[CARD_BY_ID[key]["name"] for key in ids],
                        forbidden_phrases=case.get("forbidden_phrases", []),
                        reviewer_approved=state["review"]["approved"],
                    )
                    row["quality_checks"] = assessment["checks"]
                    row["passed"] = assessment["passed"]
                    row["validated_and_reviewed"] = assessment["passed"]
                except CallBudgetExceeded:
                    row.update(passed=False, validated_and_reviewed=False,
                               failure="call_budget_exceeded")
                except Exception:
                    # No provider error, model output or user data in reports.
                    row.update(passed=False, validated_and_reviewed=False,
                               failure="generation_failed")
                row["calls"] = budget["used"] - start_calls
                row["input_tokens"] = getattr(provider, "input_tokens", 0)
                row["output_tokens"] = getattr(provider, "output_tokens", 0)
        results.append(row)

    categories = {}
    for name in sorted({row["category"] for row in results}):
        subset = [row for row in results if row["category"] == name]
        categories[name] = {
            "cases": len(subset),
            "passed": sum(row["passed"] for row in subset),
            "pass_rate": round(sum(row["passed"] for row in subset) / len(subset), 4),
        }
    status_counts = Counter("passed" if row["passed"] else "failed" for row in results)
    return {
        "schema_version": 2,
        "mode": "live" if live else "retrieval_only",
        "dataset_sha256": dataset_hash,
        "prompt_version": PROMPT_VERSION,
        "model": get_settings().llm_model if live else None,
        "cases": results,
        "summary": {
            "selected": len(results),
            "passed": status_counts["passed"],
            "failed": status_counts["failed"],
            "pass_rate": round(status_counts["passed"] / len(results), 4),
            "categories": categories,
            "calls": budget["used"],
            "input_tokens": sum(row.get("input_tokens", 0) for row in results),
            "output_tokens": sum(row.get("output_tokens", 0) for row in results),
        },
        "note": (
            "Structural and heuristic checks only; no guarantee of semantic grounding, "
            "clinical safety, forecasting or real-world accuracy. Human evaluation required."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use paid API; requires explicit budgets")
    parser.add_argument("--max-cases", type=int, help="Number of first dataset cases to run")
    parser.add_argument("--max-calls", type=int, help="Hard ceiling for paid chat calls")
    parser.add_argument("--output", type=Path, help="Write JSON report (synthetic metadata only)")
    parser.add_argument("--baseline", type=Path, help="Compare with matching JSON report")
    parser.add_argument("--min-pass-rate", type=float, default=1, help="Quality gate, 0..1")
    args = parser.parse_args()
    if not 0 <= args.min_pass_rate <= 1:
        parser.error("--min-pass-rate must be between 0 and 1")
    if args.live and (args.max_cases is None or args.max_calls is None):
        parser.error("--live requires --max-cases and --max-calls")
    if not args.live and args.max_calls is not None:
        parser.error("--max-calls requires --live")
    try:
        with Session(get_engine()) as db:
            result = evaluate(
                db, live=args.live, case_limit=args.max_cases, max_calls=args.max_calls
            )
        if args.baseline:
            baseline = json.loads(args.baseline.read_text())
            result["regressions"] = compare_reports(result, baseline)
    except (EvaluationConfigError, ValueError) as exc:
        parser.error(str(exc))
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n")
    if result["summary"]["pass_rate"] < args.min_pass_rate or result.get("regressions"):
        sys.exit(1)


if __name__ == "__main__":
    main()
