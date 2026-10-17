def validate_citations(cited_ids: list[str], retrieved_ids: set[str]) -> bool:
    return bool(cited_ids) and set(cited_ids).issubset(retrieved_ids)
