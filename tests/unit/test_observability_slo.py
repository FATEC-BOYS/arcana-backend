import pytest

from app.ai.observability import RunTrace
from scripts.observability import check_slo, percentile, percentile_95


def test_nearest_rank_percentiles_are_deterministic():
    assert percentile_95([]) is None
    assert percentile_95([2, 1, 10, 3]) == 10
    assert percentile([1, 2, 3, 4], 0.5) == 2


def test_slo_reports_insufficient_data_not_success():
    data = {"runs": 0, "completion_rate": None, "duration_ms": {"p95": None}}
    assert check_slo(data)["status"] == "insufficient_data"


def test_slo_breaches_and_healthy_boundaries():
    sample = {"runs": 40, "completion_rate": 0.9, "duration_ms": {"p95": 65000}}
    failure = check_slo(sample)
    assert failure["status"] == "breached"
    assert failure["breaches"] == ["completion_rate", "duration_p95"]
    good = check_slo({**sample, "completion_rate": 0.96,
                      "duration_ms": {"p95": 60000}})
    assert good["status"] == "healthy"


@pytest.mark.parametrize("kwargs", [
    {"min_runs": 0}, {"min_completion_rate": 1.1}, {"max_p95_ms": 0}
])
def test_invalid_slo_thresholds_fail_closed(kwargs):
    with pytest.raises(ValueError):
        check_slo({"runs": 50}, **kwargs)


def test_agent_spans_include_only_numeric_provider_metadata():
    class Counter:
        calls = input_tokens = output_tokens = embedding_tokens = 0

    provider = Counter()
    trace = RunTrace()
    with trace.step("interpret", provider=provider):
        provider.calls += 1
        provider.input_tokens += 125
        provider.output_tokens += 35
    with pytest.raises(RuntimeError):
        with trace.step("review", provider=provider):
            provider.calls += 1
            raise RuntimeError("PRIVATE USER SECRET")
    result = trace.as_dict()
    assert result["steps"][0]["input_tokens"] == 125
    assert result["steps"][0]["output_tokens"] == 35
    assert result["steps"][1]["calls"] == 1
    assert result["steps"][1]["status"] == "error"
    assert "PRIVATE USER SECRET" not in str(result)
