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
from app.ai.judge import JUDGE_VERSION, grade_reading
from app.ai.orchestration.graph import build_reading_graph
from app.ai.prompts.templates import PROMPT_VERSION
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import get_settings
from app.db.session import get_engine
from app.modules.cards.catalog import CARD_BY_ID
from app.rag.retrieval import search
from app.rag.seed import PLANET_THEMES, SIGNS

DATASET = Path(__file__).resolve().parents[1] / "evaluations/datasets/tarot.json"
ASTRO_DATASET = Path(__file__).resolve().parents[1] / "evaluations/datasets/astrology.json"
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



def load_astrology_cases(path=ASTRO_DATASET):
    raw = Path(path).read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise EvaluationConfigError("invalid_astrology_dataset_size")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationConfigError("invalid_astrology_case")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise EvaluationConfigError("duplicate_or_missing_astrology_id")
        if case.get("kind") != "astrology":
            raise EvaluationConfigError("invalid_astrology_kind")
        if not isinstance(case.get("category"), str) or not case["category"]:
            raise EvaluationConfigError("invalid_astrology_category")
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise EvaluationConfigError("invalid_astrology_question")
        facts = case.get("facts")
        if not isinstance(facts, dict) or not isinstance(facts.get("birth_time_known"), bool):
            raise EvaluationConfigError("invalid_astrology_facts")
        planets = facts.get("planets")
        if not isinstance(planets, dict) or not planets or not set(planets) <= PLANET_THEMES.keys():
            raise EvaluationConfigError("invalid_astrology_planets")
        if not all(
            isinstance(planet, dict) and planet.get("sign") in SIGNS.values().__class__
            for planet in []
        ):
            raise EvaluationConfigError("invalid_astrology_sign")
        if any(not isinstance(p, dict) or p.get("sign") not in SIGNS for p in planets.values()):
            raise EvaluationConfigError("invalid_astrology_sign")
        ids = case.get("fact_ids")
        tags = case.get("retrieval_tags")
        if ids != list(planets) or not isinstance(tags, list) or not all(
            isinstance(tag, str) for tag in tags
        ):
            raise EvaluationConfigError("invalid_astrology_ids")
        if not set(ids) <= set(tags):
            raise EvaluationConfigError("astrology_tags_do_not_cover_facts")
        forbidden = case.get("forbidden_phrases", [])
        if not isinstance(forbidden, list) or any(
            not isinstance(phrase, str) or not phrase for phrase in forbidden
        ):
            raise EvaluationConfigError("invalid_astrology_forbidden_phrases")
        seen.add(case_id)
    return cases, hashlib.sha256(raw).hexdigest()


def select_suites(suite, *, tarot_dataset=DATASET, astrology_dataset=ASTRO_DATASET):
    if suite not in {"tarot", "astrology", "all"}:
        raise EvaluationConfigError("invalid_suite")
    selected = []
    checksums = []
    if suite in {"tarot", "all"}:
        tarot, digest = load_cases(tarot_dataset)
        selected.extend(tarot)
        checksums.append(digest)
    if suite in {"astrology", "all"}:
        astrology, digest = load_astrology_cases(astrology_dataset)
        selected.extend(astrology)
        checksums.append(digest)
    if len({case["id"] for case in selected}) != len(selected):
        raise EvaluationConfigError("duplicate_cross_suite_ids")
    checksum = checksums[0] if len(checksums) == 1 else hashlib.sha256(
        ":".join(checksums).encode()
    ).hexdigest()
    return selected, checksum


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
    provider_factory=OpenAIProvider, dataset=DATASET, suite="all",
    astrology_dataset=ASTRO_DATASET, judge=False, judge_provider_factory=None,
    judge_model=None,
):
    cases, dataset_hash = select_suites(
        suite, tarot_dataset=dataset, astrology_dataset=astrology_dataset
    )
    if case_limit is not None and not 1 <= case_limit <= len(cases):
        raise EvaluationConfigError("invalid_case_limit")
    if judge and not live:
        raise EvaluationConfigError("judge_requires_live_mode")
    per_case = 5 if judge else 4
    if live and (
        case_limit is None or max_calls is None or max_calls < per_case * case_limit
    ):
        raise EvaluationConfigError("live_requires_explicit_calls_budget_per_selected_case")
    selected = cases[:case_limit] if case_limit is not None else cases
    budget = {"limit": max_calls or 0, "used": 0}
    results = []
    for case in selected:
        kind = case.get("kind", "tarot")
        if kind == "tarot":
            ids = case["card_ids"]
            tags = ids
            facts = {
                "cards": [
                    {"card_id": key, "name": CARD_BY_ID[key]["name"], "reversed": False}
                    for key in ids
                ]
            }
            symbols = [CARD_BY_ID[key]["name"] for key in ids]
        else:
            ids = case["fact_ids"]
            tags = case["retrieval_tags"]
            facts = case["facts"]
            symbols = case.get("required_mentions", [])
        sources = search(db, topic=kind, tags=tags)
        coverage = all(any(
            (f":{id_}:" if kind == "astrology" else id_) in item.source_id
            for item in sources
        ) for id_ in ids)
        row = {
            "id": case["id"],
            "suite": kind,
            "category": case["category"],
            "retrieval_coverage": coverage,
            "source_count": len(sources),
            "passed": coverage,
        }
        if live:
            if not coverage:
                row.update(passed=False, validated_and_reviewed=False, failure="missing_evidence")
            else:
                provider = provider_factory()
                guarded = BudgetedProvider(provider, budget)
                judge_provider = None
                start_calls = budget["used"]
                try:
                    payload = {
                        "question": case["question"],
                        "facts": facts,
                        "fact_ids": ids,
                        "sources": [asdict(item) for item in sources],
                        "history": [],
                        "original_reading": None,
                    }
                    state = build_reading_graph(guarded).invoke(
                        {"payload": payload, "corrections": -1}
                    )
                    assessment = assess_answer(
                        state["answer"],
                        allowed_source_ids={source.source_id for source in sources},
                        allowed_fact_ids=set(ids),
                        card_names=symbols,
                        forbidden_phrases=case.get("forbidden_phrases", []),
                        reviewer_approved=state["review"]["approved"],
                    )
                    row["quality_checks"] = assessment["checks"]
                    row["validated_and_reviewed"] = assessment["passed"]
                    row["passed"] = assessment["passed"]
                    if judge:
                        factory = judge_provider_factory or provider_factory
                        judge_provider = factory()
                        if judge_model is not None:
                            judge_provider.model = judge_model
                        grade = grade_reading(
                            BudgetedProvider(judge_provider, budget),
                            question=case["question"],
                            facts=facts,
                            sources=[asdict(item) for item in sources],
                            answer=state["answer"],
                            category=case["category"],
                        )
                        row["judge"] = {
                            "version": JUDGE_VERSION,
                            "scores": grade.model_dump(),
                            "passed": grade.passed(),
                        }
                        row["passed"] = row["passed"] and grade.passed()
                except CallBudgetExceeded:
                    row.update(passed=False, validated_and_reviewed=False,
                               failure="call_budget_exceeded")
                except Exception:
                    # No provider error messages, prompts or generations in reports.
                    row.update(passed=False, validated_and_reviewed=False,
                               failure="generation_or_judge_failed")
                row["calls"] = budget["used"] - start_calls
                row["input_tokens"] = getattr(provider, "input_tokens", 0) + (
                    getattr(judge_provider, "input_tokens", 0) if judge_provider else 0
                )
                row["output_tokens"] = getattr(provider, "output_tokens", 0) + (
                    getattr(judge_provider, "output_tokens", 0) if judge_provider else 0
                )
        results.append(row)

    categories = {}
    for name in sorted({(row["suite"], row["category"]) for row in results}):
        subset = [row for row in results if (row["suite"], row["category"]) == name]
        categories[f"{name[0]}/{name[1]}"] = {
            "cases": len(subset),
            "passed": sum(row["passed"] for row in subset),
            "pass_rate": round(sum(row["passed"] for row in subset) / len(subset), 4),
        }
    status_counts = Counter("passed" if row["passed"] else "failed" for row in results)
    return {
        "schema_version": 3,
        "mode": "live" if live else "retrieval_only",
        "suite": suite,
        "dataset_sha256": dataset_hash,
        "prompt_version": PROMPT_VERSION,
        "model": get_settings().llm_model if live else None,
        "judge_version": JUDGE_VERSION if judge else None,
        "judge_model": (judge_model or get_settings().llm_model) if judge else None,
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
            "Structural, heuristic and optional subjective judge scores only. "
            "Human evaluation required before release."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use paid API; requires explicit budgets")
    parser.add_argument("--max-cases", type=int, help="Number of first dataset cases to run")
    parser.add_argument("--max-calls", type=int, help="Hard ceiling for paid chat calls")
    parser.add_argument("--suite", choices=("all", "tarot", "astrology"), default="all")
    parser.add_argument("--judge", action="store_true", help="Optional paid rubric judge")
    parser.add_argument("--judge-model", help="Optional independent model for the judge")
    parser.add_argument("--output", type=Path, help="Write JSON report (synthetic metadata only)")
    parser.add_argument("--baseline", type=Path, help="Compare with matching JSON report")
    parser.add_argument("--min-pass-rate", type=float, default=1, help="Quality gate, 0..1")
    args = parser.parse_args()
    if not 0 <= args.min_pass_rate <= 1:
        parser.error("--min-pass-rate must be between 0 and 1")
    if args.judge_model and not args.judge:
        parser.error("--judge-model requires --judge")
    if args.judge and not args.live:
        parser.error("--judge requires --live")
    if args.live and (args.max_cases is None or args.max_calls is None):
        parser.error("--live requires --max-cases and --max-calls")
    if not args.live and args.max_calls is not None:
        parser.error("--max-calls requires --live")
    try:
        with Session(get_engine()) as db:
            result = evaluate(
                db, live=args.live, case_limit=args.max_cases, max_calls=args.max_calls,
                suite=args.suite, judge=args.judge, judge_model=args.judge_model,
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
