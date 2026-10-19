"""Operational SLO checks using only sanitized, aggregated generation metadata."""

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from math import ceil
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GenerationRun
from app.db.session import get_engine

STAGE_NAMES = frozenset({"retrieval", "interpret", "review", "reject"})
COUNTER_NAMES = ("calls", "input_tokens", "output_tokens", "embedding_tokens")


def percentile(values, level):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, ceil(level * len(ordered)) - 1)], 2)


def percentile_95(values):
    return percentile(values, 0.95)


def report(db, *, days=7, now_ts=None):
    if not 1 <= days <= 365:
        raise ValueError("days must be between 1 and 365")
    current = int(time.time()) if now_ts is None else int(now_ts)
    runs = list(
        db.scalars(
            select(GenerationRun).where(
                GenerationRun.created_at >= current - days * 86400,
                GenerationRun.created_at <= current,
            )
        )
    )
    statuses = Counter(row.status for row in runs)
    errors = Counter(row.error_code for row in runs if row.error_code)
    latencies = [row.duration_ms for row in runs if row.duration_ms is not None]
    stage_durations = defaultdict(list)
    stage_errors = Counter()
    stage_counters = defaultdict(Counter)
    by_model = defaultdict(Counter)
    by_day = defaultdict(Counter)
    review_rejections = 0
    review_total = 0
    for row in runs:
        model = row.model or "unknown"
        by_model[model]["runs"] += 1
        by_model[model][row.status] += 1
        by_model[model]["input_tokens"] += row.input_tokens or 0
        by_model[model]["output_tokens"] += row.output_tokens or 0
        utc_day = time.strftime("%Y-%m-%d", time.gmtime(row.created_at))
        by_day[utc_day]["runs"] += 1
        by_day[utc_day][row.status] += 1
        trace = row.trace if isinstance(row.trace, dict) else {}
        review_rejections += trace.get("review_rejections", 0)
        review_total += len(trace.get("review_outcomes", []))
        for step in trace.get("steps", []):
            if not isinstance(step, dict) or step.get("stage") not in STAGE_NAMES:
                continue
            stage = step["stage"]
            stage_durations[stage].append(max(0, step.get("duration_ms", 0)))
            if step.get("status") == "error":
                stage_errors[stage] += 1
            for metric in COUNTER_NAMES:
                stage_counters[stage][metric] += max(0, step.get(metric, 0))
    attempts = len(runs)
    return {
        "window_days": days,
        "runs": attempts,
        "statuses": dict(sorted(statuses.items())),
        "completion_rate": round(statuses["completed"] / attempts, 4) if attempts else None,
        "duration_ms": {
            "median": round(median(latencies), 2) if latencies else None,
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "tokens": {
            "input": sum(row.input_tokens or 0 for row in runs),
            "output": sum(row.output_tokens or 0 for row in runs),
            "embedding": sum(row.embedding_tokens or 0 for row in runs),
        },
        "provider_calls": sum(row.calls or 0 for row in runs),
        "model_calls": sum(row.calls or 0 for row in runs),  # Backwards compatibility.
        "review_rejections": review_rejections,
        "review_decisions": review_total,
        "review_rejection_rate": (
            round(review_rejections / review_total, 4) if review_total else None
        ),
        "stages": {
            stage: {
                "calls": len(values),
                "p50_ms": percentile(values, 0.5),
                "p95_ms": percentile(values, 0.95),
                "errors": stage_errors[stage],
                "usage": dict(stage_counters[stage]),
            }
            for stage, values in sorted(stage_durations.items())
        },
        "by_model": {name: dict(counts) for name, counts in sorted(by_model.items())},
        "daily": {date: dict(counts) for date, counts in sorted(by_day.items())},
        "errors": dict(sorted(errors.items())),
        "note": (
            "Counts attempts, not distinct readings. Sensitive content and identifiers excluded."
        ),
    }


def check_slo(metrics, *, min_runs=20, min_completion_rate=0.95, max_p95_ms=60000):
    """Return explicit insufficient-data state instead of claiming an empty system is healthy."""
    if min_runs < 1 or not 0 <= min_completion_rate <= 1 or max_p95_ms <= 0:
        raise ValueError("invalid_slo_thresholds")
    if metrics["runs"] < min_runs:
        return {
            "status": "insufficient_data",
            "sample_size": metrics["runs"],
            "min_runs": min_runs,
            "breaches": [],
        }
    breaches = []
    if metrics["completion_rate"] < min_completion_rate:
        breaches.append("completion_rate")
    if (
        metrics["duration_ms"]["p95"] is not None
        and metrics["duration_ms"]["p95"] > max_p95_ms
    ):
        breaches.append("duration_p95")
    return {
        "status": "breached" if breaches else "healthy",
        "sample_size": metrics["runs"],
        "min_runs": min_runs,
        "breaches": breaches,
        "thresholds": {
            "min_completion_rate": min_completion_rate,
            "max_p95_ms": max_p95_ms,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--min-runs", type=int, default=20)
    parser.add_argument("--min-completion-rate", type=float, default=0.95)
    parser.add_argument("--max-p95-ms", type=float, default=60000)
    parser.add_argument("--fail-on-breach", action="store_true")
    parser.add_argument("--fail-on-insufficient-data", action="store_true")
    args = parser.parse_args()
    try:
        with Session(get_engine()) as db:
            output = report(db, days=args.days)
        output["slo"] = check_slo(
            output,
            min_runs=args.min_runs,
            min_completion_rate=args.min_completion_rate,
            max_p95_ms=args.max_p95_ms,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if args.fail_on_breach and output["slo"]["status"] == "breached":
        sys.exit(1)
    if args.fail_on_insufficient_data and output["slo"]["status"] == "insufficient_data":
        sys.exit(2)


if __name__ == "__main__":
    main()
