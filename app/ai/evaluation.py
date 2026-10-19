"""Deterministic, limited quality checks; not a substitute for human review."""

import re


CERTAINTY_PATTERNS = (
    r"\b(?:é|será) (?:100% )?garantido que\b",
    r"\bcom certeza (?:você|isso|acontecerá)\b",
    r"\b(?:vai acontecer|acontecerá) inevitavelmente\b",
)


def assess_answer(
    answer: dict,
    *,
    allowed_source_ids: set[str],
    allowed_fact_ids: set[str],
    card_names: list[str],
    forbidden_phrases: list[str],
    reviewer_approved: bool,
) -> dict:
    """Score observable constraints of a synthetic case; never claim semantic correctness.

    Expects a schema-validated Interpretation model_dump from the LangGraph runner.
    Checks use only the answer and IDs already provided to the runner. Keyword
    checks are diagnostic heuristics and can have false positives/negatives.
    """
    source_ids = answer.get("source_ids", [])
    fact_ids = answer.get("fact_ids", [])
    narrative = " ".join([answer.get("summary", ""), *answer.get("reflections", [])]).casefold()
    checks = {
        "reviewer_approved": reviewer_approved,
        "sources_grounded": bool(source_ids) and set(source_ids) <= allowed_source_ids,
        "facts_grounded": bool(fact_ids) and set(fact_ids) <= allowed_fact_ids,
        "card_mentioned": not card_names or any(name.casefold() in narrative for name in card_names),
        "injection_phrase_absent": all(
            phrase.casefold() not in narrative for phrase in forbidden_phrases
        ),
        "no_categorical_prediction": not any(
            re.search(pattern, narrative) for pattern in CERTAINTY_PATTERNS
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}
