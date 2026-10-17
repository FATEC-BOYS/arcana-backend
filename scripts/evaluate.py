"""Synthetic retrieval checks by default; --live explicitly calls the paid model."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.orchestration.graph import build_reading_graph
from app.ai.providers.openai_provider import OpenAIProvider
from app.db.session import get_engine
from app.modules.cards.catalog import CARD_BY_ID
from app.rag.retrieval import search


def evaluate(db, *, live=False):
    dataset = json.loads(
        (Path(__file__).resolve().parents[1] / "evaluations/datasets/tarot.json").read_text()
    )
    results = []
    for case in dataset:
        ids = case["card_ids"]
        sources = search(db, topic="tarot", tags=ids)
        facts = {
            "cards": [
                {"card_id": id_, "name": CARD_BY_ID[id_]["name"], "reversed": False} for id_ in ids
            ]
        }
        coverage = all(any(id_ in evidence.source_id for evidence in sources) for id_ in ids)
        result = {
            "id": case["id"],
            "retrieval_coverage": coverage,
            "source_count": len(sources),
            "live": live,
        }
        if live:
            provider = OpenAIProvider()
            try:
                build_reading_graph(provider).invoke(
                    {
                        "payload": {
                            "question": case["question"],
                            "facts": facts,
                            "fact_ids": ids,
                            "sources": [asdict(s) for s in sources],
                            "history": [],
                            "original_reading": None,
                        },
                        "corrections": -1,
                    }
                )
                result["validated_and_reviewed"] = True
            except RuntimeError:
                result["validated_and_reviewed"] = False
            result["calls"] = provider.calls
            result["input_tokens"], result["output_tokens"] = (
                provider.input_tokens,
                provider.output_tokens,
            )
        results.append(result)
    return {
        "mode": "live" if live else "retrieval_only",
        "cases": results,
        "note": "Structural/retrieval checks do not measure semantic or scientific correctness.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live", action="store_true", help="Calls configured OpenAI model: up to 12 chat calls"
    )
    args = parser.parse_args()
    with Session(get_engine()) as db:
        report = evaluate(db, live=args.live)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not all(
            case["retrieval_coverage"] and case.get("validated_and_reviewed", True)
            for case in report["cases"]
        ):
            sys.exit(1)
