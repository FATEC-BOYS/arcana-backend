"""Aggregate operational metrics without exposing users, prompts or generated text."""

import argparse
import json
import time
from collections import Counter, defaultdict
from math import ceil
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GenerationRun
from app.db.session import get_engine


def percentile_95(values):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[ceil(0.95 * len(ordered)) - 1], 2)


def report(db, *, days=7, now_ts=None):
    if not 1 <= days <= 365:
        raise ValueError("days must be between 1 and 365")
    current = int(time.time()) if now_ts is None else int(now_ts)
    runs = list(
        db.scalars(
            select(GenerationRun).where(GenerationRun.created_at >= current - days * 86400)
        )
    )
    statuses = Counter(row.status for row in runs)
    errors = Counter(row.error_code for row in runs if row.error_code)
    latencies = [row.duration_ms for row in runs if row.duration_ms is not None]
    stage_durations = defaultdict(list)
    stage_errors = Counter()
    review_rejections = 0
    for row in runs:
        trace = row.trace or {}
        review_rejections += trace.get("review_rejections", 0)
        for step in trace.get("steps", []):
            stage = step.get("stage")
            if stage not in {"retrieval", "interpret", "review", "reject"}:
                continue
            stage_durations[stage].append(step.get("duration_ms", 0))
            if step.get("status") == "error":
                stage_errors[stage] += 1
    return {
        "window_days": days,
        "runs": len(runs),
        "statuses": dict(statuses),
        "completion_rate": round(statuses["completed"] / len(runs), 4) if runs else None,
        "duration_ms": {
            "median": round(median(latencies), 2) if latencies else None,
            "p95": percentile_95(latencies),
        },
        "tokens": {
            "input": sum(row.input_tokens or 0 for row in runs),
            "output": sum(row.output_tokens or 0 for row in runs),
            "embedding": sum(row.embedding_tokens or 0 for row in runs),
        },
        "model_calls": sum(row.calls or 0 for row in runs),
        "review_rejections": review_rejections,
        "stages": {
            stage: {
                "calls": len(values),
                "p95_ms": percentile_95(values),
                "errors": stage_errors[stage],
            }
            for stage, values in sorted(stage_durations.items())
        },
        "errors": dict(errors),
        "note": "Aggregates only. No content, user IDs, prompts, sources or answers.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="Rolling UTC window, 1 to 365 days")
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")
    with Session(get_engine()) as db:
        print(json.dumps(report(db, days=args.days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
