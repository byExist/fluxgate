"""Tests for tripper conditions (Closed, HalfOpened, MinRequests, FailureRate, etc.)."""

import pytest

from fluxgate.trippers import (
    Closed,
    HalfOpened,
    MinRequests,
    FailureRate,
    AvgLatency,
    SlowRate,
    FailureStreak,
)
from fluxgate.metric import Metric
from fluxgate.state import StateEnum


def test_min_requests_invalid_count():
    """MinRequests rejects invalid count."""
    with pytest.raises(ValueError, match="Count must be greater than zero"):
        MinRequests(count=0)

    with pytest.raises(ValueError, match="Count must be greater than zero"):
        MinRequests(count=-5)


def test_failure_rate_invalid_ratio():
    """FailureRate rejects invalid ratio."""
    with pytest.raises(ValueError, match="Ratio must be between 0 and 1"):
        FailureRate(ratio=0.0)

    with pytest.raises(ValueError, match="Ratio must be between 0 and 1"):
        FailureRate(ratio=1.5)


def test_avg_latency_invalid_threshold():
    """AvgLatency rejects invalid threshold."""
    with pytest.raises(ValueError, match="Threshold must be greater than 0"):
        AvgLatency(threshold=0.0)

    with pytest.raises(ValueError, match="Threshold must be greater than 0"):
        AvgLatency(threshold=-1.0)


def test_slow_call_rate_invalid_ratio():
    """SlowRate rejects invalid ratio."""
    with pytest.raises(ValueError, match="Ratio must be between 0 and 1"):
        SlowRate(ratio=0.0)

    with pytest.raises(ValueError, match="Ratio must be between 0 and 1"):
        SlowRate(ratio=1.5)


def test_closed_and_halfopened_state_checks():
    """Closed and HalfOpened check circuit state."""
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=2)

    # Closed tripper
    tripper = Closed()
    assert tripper(metric, StateEnum.CLOSED, 0) is True
    assert tripper(metric, StateEnum.HALF_OPEN, 0) is False
    assert tripper(metric, StateEnum.OPEN, 0) is False

    # HalfOpened tripper
    tripper = HalfOpened()
    assert tripper(metric, StateEnum.HALF_OPEN, 0) is True
    assert tripper(metric, StateEnum.CLOSED, 0) is False
    assert tripper(metric, StateEnum.OPEN, 0) is False


def test_min_requests():
    """MinRequests requires minimum number of calls."""
    tripper = MinRequests(count=10)

    # Below threshold
    metric = Metric(total_count=5, failure_count=3, total_duration=5.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # At threshold
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # Above threshold
    metric = Metric(total_count=15, failure_count=8, total_duration=15.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_failure_rate():
    """FailureRate trips when failure ratio exceeds threshold."""
    tripper = FailureRate(ratio=0.5)

    # Below threshold (3/10 = 30%)
    metric = Metric(total_count=10, failure_count=3, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # At threshold (5/10 = 50%)
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # Above threshold (7/10 = 70%)
    metric = Metric(total_count=10, failure_count=7, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_avg_latency():
    """AvgLatency trips when average duration reaches or exceeds threshold."""
    tripper = AvgLatency(threshold=1.0)

    # Below threshold (5.0 / 10 = 0.5s avg)
    metric = Metric(total_count=10, failure_count=0, total_duration=5.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # At threshold (10.0 / 10 = 1.0s avg)
    metric = Metric(total_count=10, failure_count=0, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # Above threshold (15.0 / 10 = 1.5s avg)
    metric = Metric(total_count=10, failure_count=0, total_duration=15.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_slow_call_rate():
    """SlowRate trips when slow call ratio exceeds threshold."""
    tripper = SlowRate(ratio=0.3)

    # Below threshold (2/10 = 20%)
    metric = Metric(total_count=10, failure_count=0, total_duration=10.0, slow_count=2)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # At threshold (3/10 = 30%)
    metric = Metric(total_count=10, failure_count=0, total_duration=10.0, slow_count=3)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # Above threshold (5/10 = 50%)
    metric = Metric(total_count=10, failure_count=0, total_duration=10.0, slow_count=5)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_and_operator():
    """AND operator requires all conditions to be true."""
    # Common pattern: MinRequests & FailureRate
    tripper = MinRequests(10) & FailureRate(0.5)

    # Fails MinRequests (5 < 10)
    metric = Metric(total_count=5, failure_count=3, total_duration=5.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # Passes MinRequests but fails FailureRate (3/10 = 30% < 50%)
    metric = Metric(total_count=10, failure_count=3, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # Passes both (10 >= 10 and 5/10 = 50%)
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_or_operator():
    """OR operator succeeds if any condition is true."""
    # Trip if either failure rate or slow call rate is high
    tripper = FailureRate(0.5) | SlowRate(0.3)

    # Neither condition met
    metric = Metric(total_count=10, failure_count=2, total_duration=10.0, slow_count=1)
    assert tripper(metric, StateEnum.CLOSED, 0) is False

    # Only FailureRate met (5/10 = 50%)
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=1)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # Only SlowRate met (3/10 = 30%)
    metric = Metric(total_count=10, failure_count=2, total_duration=10.0, slow_count=3)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # Both met
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=3)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_trippers_with_empty_metrics():
    """Trippers handle empty metrics (total_count=0) correctly."""
    empty_metric = Metric(
        total_count=0, failure_count=0, total_duration=0.0, slow_count=0
    )

    # MinRequests should fail
    assert MinRequests(10)(empty_metric, StateEnum.CLOSED, 0) is False

    # Ratio-based trippers should not trip on empty metrics
    assert FailureRate(0.5)(empty_metric, StateEnum.CLOSED, 0) is False
    assert AvgLatency(1.0)(empty_metric, StateEnum.CLOSED, 0) is False
    assert SlowRate(0.3)(empty_metric, StateEnum.CLOSED, 0) is False


def test_nested_logical_operators():
    """Logical operators can be nested (AND of AND, OR of OR)."""
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)

    # (A & B) & C - all three must pass
    tripper = (MinRequests(5) & FailureRate(0.5)) & MinRequests(10)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # (A | B) | C - any one must pass
    tripper = (MinRequests(20) | FailureRate(0.5)) | MinRequests(5)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_mixed_logical_operators():
    """Mixed AND/OR operators can be combined."""
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)

    # (A & B) | C - either (A and B) or C
    tripper = (MinRequests(5) & FailureRate(0.5)) | MinRequests(20)
    assert tripper(metric, StateEnum.CLOSED, 0) is True

    # (A | B) & C - (A or B) and C
    tripper = (MinRequests(20) | FailureRate(0.5)) & MinRequests(10)
    assert tripper(metric, StateEnum.CLOSED, 0) is True


def test_failure_streak_invalid_count():
    """FailureStreak rejects invalid count."""
    with pytest.raises(ValueError, match="Count must be greater than zero"):
        FailureStreak(count=0)

    with pytest.raises(ValueError, match="Count must be greater than zero"):
        FailureStreak(count=-5)


def test_failure_streak():
    """FailureStreak trips when consecutive failure count reaches threshold."""
    tripper = FailureStreak(count=5)
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)

    # Below threshold
    assert tripper(metric, StateEnum.CLOSED, consecutive_failures=3) is False

    # At threshold
    assert tripper(metric, StateEnum.CLOSED, consecutive_failures=5) is True

    # Above threshold
    assert tripper(metric, StateEnum.CLOSED, consecutive_failures=7) is True


def test_failure_streak_with_or():
    """FailureStreak can be combined with OR for fast failure detection."""
    # Trip on 5 consecutive failures OR (20 requests with 50% failure rate)
    tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))
    metric = Metric(total_count=10, failure_count=5, total_duration=10.0, slow_count=0)

    # Neither condition met
    assert tripper(metric, StateEnum.CLOSED, consecutive_failures=3) is False

    # Only ConsecutiveFailures met (fast path)
    assert tripper(metric, StateEnum.CLOSED, consecutive_failures=5) is True

    # Only MinRequests & FailureRate met
    metric = Metric(total_count=20, failure_count=10, total_duration=20.0, slow_count=0)
    assert tripper(metric, StateEnum.CLOSED, consecutive_failures=2) is True
