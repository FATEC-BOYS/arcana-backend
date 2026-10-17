"""Future LangGraph flow: retrieve -> interpret -> review -> optional correction.
Draw and persistence happen before this flow; at most one correction is permitted.
"""
from app.core.exceptions import FeatureNotImplementedError


def build_reading_graph():
    raise FeatureNotImplementedError("Wire providers, retrieval and review before enabling")
