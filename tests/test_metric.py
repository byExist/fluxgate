"""Tests for Metric computed properties and monoid operations."""

from fluxgate.metric import Metric, Record


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


def test_metric_empty_is_zero():
    """Metric.empty() is the additive identity (zero element)."""
    empty = Metric.empty()
    assert empty.total_count == 0
    assert empty.failure_count == 0
    assert empty.total_duration == 0.0
    assert empty.slow_counts == {}


def test_metric_empty_is_identity_under_addition():
    """For any metric m: m + empty == m == empty + m."""
    m = Metric(
        total_count=10,
        failure_count=3,
        total_duration=5.0,
        slow_counts={1.0: 2},
    )
    assert m + Metric.empty() == m
    assert Metric.empty() + m == m


def test_metric_from_record_success_without_slow():
    """from_record contributes one successful, non-slow call."""
    metric = Metric.from_record(Record(success=True, duration=0.5, slow_at=()))
    assert metric.total_count == 1
    assert metric.failure_count == 0
    assert metric.total_duration == 0.5
    assert metric.slow_counts == {}


def test_metric_from_record_failure_with_multiple_slow_thresholds():
    """from_record records a failure with one increment per exceeded threshold."""
    metric = Metric.from_record(Record(success=False, duration=2.5, slow_at=(1.0, 2.0)))
    assert metric.total_count == 1
    assert metric.failure_count == 1
    assert metric.total_duration == 2.5
    assert metric.slow_counts == {1.0: 1, 2.0: 1}


def test_metric_addition_merges_slow_counts():
    """Adding metrics sums totals and merges per-threshold slow counters."""
    left = Metric(
        total_count=2,
        failure_count=1,
        total_duration=1.0,
        slow_counts={1.0: 1, 3.0: 1},
    )
    right = Metric(
        total_count=3,
        failure_count=0,
        total_duration=2.0,
        slow_counts={1.0: 2, 5.0: 1},
    )

    result = left + right
    assert result.total_count == 5
    assert result.failure_count == 1
    assert result.total_duration == 3.0
    assert result.slow_counts == {1.0: 3, 3.0: 1, 5.0: 1}


def test_metric_subtraction_inverts_addition():
    """For any a, b: (a + b) - b == a."""
    a = Metric(
        total_count=5,
        failure_count=2,
        total_duration=3.0,
        slow_counts={1.0: 1},
    )
    b = Metric.from_record(Record(success=False, duration=0.5, slow_at=(1.0,)))

    assert (a + b) - b == a


def test_metric_subtraction_drops_zeroed_slow_keys():
    """Slow-count keys that hit zero are removed, not left as {threshold: 0}."""
    a = Metric(
        total_count=1,
        failure_count=0,
        total_duration=1.0,
        slow_counts={1.0: 1},
    )
    b = Metric(
        total_count=1,
        failure_count=0,
        total_duration=1.0,
        slow_counts={1.0: 1},
    )

    result = a - b
    assert result.slow_counts == {}
