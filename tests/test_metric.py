"""Tests for Metric computed properties."""

from fluxgate.metric import Metric


def test_metric_computed_properties_with_data():
    """Metric computed properties return correct values when data exists."""
    metric = Metric(
        total_count=100,
        failure_count=20,
        total_duration=50.0,
        slow_count=10,
    )

    assert metric.avg_duration == 0.5  # 50.0 / 100
    assert metric.failure_rate == 0.2  # 20 / 100
    assert metric.slow_rate == 0.1  # 10 / 100


def test_metric_computed_properties_empty():
    """Metric computed properties return None when no data exists."""
    metric = Metric(
        total_count=0,
        failure_count=0,
        total_duration=0.0,
        slow_count=0,
    )

    assert metric.avg_duration is None
    assert metric.failure_rate is None
    assert metric.slow_rate is None


def test_metric_computed_properties_edge_cases():
    """Metric computed properties handle edge cases correctly."""
    # All successes
    metric = Metric(
        total_count=100,
        failure_count=0,
        total_duration=25.0,
        slow_count=0,
    )
    assert metric.avg_duration == 0.25
    assert metric.failure_rate == 0.0
    assert metric.slow_rate == 0.0

    # All failures
    metric = Metric(
        total_count=50,
        failure_count=50,
        total_duration=100.0,
        slow_count=50,
    )
    assert metric.avg_duration == 2.0
    assert metric.failure_rate == 1.0
    assert metric.slow_rate == 1.0
