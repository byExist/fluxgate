"""Tests for Metric computed properties."""

from fluxgate.metric import Metric


def test_metric_computed_properties_with_data():
    """Metric computed properties return correct values when data exists."""
    metric = Metric(
        total_count=100,
        failure_count=20,
        total_duration=50.0,
        slow_counts={1.0: 10, 5.0: 2},
    )

    assert metric.avg_duration == 0.5  # 50.0 / 100
    assert metric.failure_rate == 0.2  # 20 / 100
    assert metric.slow_rate(1.0) == 0.1  # 10 / 100
    assert metric.slow_rate(5.0) == 0.02  # 2 / 100


def test_metric_computed_properties_empty():
    """Metric computed properties return None when no data exists."""
    metric = Metric(
        total_count=0,
        failure_count=0,
        total_duration=0.0,
        slow_counts={1.0: 0},
    )

    assert metric.avg_duration is None
    assert metric.failure_rate is None
    assert metric.slow_rate(1.0) is None


def test_metric_slow_rate_unregistered_threshold_is_zero():
    """slow_rate for a threshold not present in slow_counts is treated as zero."""
    metric = Metric(
        total_count=100,
        failure_count=0,
        total_duration=50.0,
        slow_counts={1.0: 10},
    )

    # Threshold 5.0 was never recorded; rate is 0, not None.
    assert metric.slow_rate(5.0) == 0.0


def test_metric_computed_properties_edge_cases():
    """Metric computed properties handle edge cases correctly."""
    # All successes
    metric = Metric(
        total_count=100,
        failure_count=0,
        total_duration=25.0,
        slow_counts={1.0: 0},
    )
    assert metric.avg_duration == 0.25
    assert metric.failure_rate == 0.0
    assert metric.slow_rate(1.0) == 0.0

    # All failures, all slow
    metric = Metric(
        total_count=50,
        failure_count=50,
        total_duration=100.0,
        slow_counts={1.0: 50},
    )
    assert metric.avg_duration == 2.0
    assert metric.failure_rate == 1.0
    assert metric.slow_rate(1.0) == 1.0
