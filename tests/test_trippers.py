"""Tests for tripper conditions (Closed, HalfOpened, MinRequests, FailureRate, etc.)."""

import pytest

from fluxgate.trippers import (
    CallContext,
    Closed,
    HalfOpened,
    MinRequests,
    FailureRate,
    AvgLatency,
    SlowRate,
    FailureStreak,
)
from fluxgate.metric import Metric
from fluxgate.state import State


def _ctx(metric: Metric, state: State, consecutive_failures: int = 0) -> CallContext:
    return CallContext(
        metric=metric, state=state, consecutive_failures=consecutive_failures
    )


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
        SlowRate(ratio=0.0, threshold=1.0)

    with pytest.raises(ValueError, match="Ratio must be between 0 and 1"):
        SlowRate(ratio=1.5, threshold=1.0)


def test_slow_call_rate_invalid_threshold():
    """SlowRate rejects invalid threshold."""
    with pytest.raises(ValueError, match="Threshold must be greater than 0"):
        SlowRate(ratio=0.3, threshold=0.0)

    with pytest.raises(ValueError, match="Threshold must be greater than 0"):
        SlowRate(ratio=0.3, threshold=-1.0)


def test_closed_and_halfopened_state_checks():
    """Closed and HalfOpened check circuit state."""
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )

    # Closed tripper
    tripper = Closed()
    assert tripper(_ctx(metric, "closed")) is True
    assert tripper(_ctx(metric, "half_open")) is False
    assert tripper(_ctx(metric, "open")) is False

    # HalfOpened tripper
    tripper = HalfOpened()
    assert tripper(_ctx(metric, "half_open")) is True
    assert tripper(_ctx(metric, "closed")) is False
    assert tripper(_ctx(metric, "open")) is False


def test_min_requests():
    """MinRequests requires minimum number of calls."""
    tripper = MinRequests(count=10)

    # Below threshold
    metric = Metric(total_count=5, failure_count=3, total_duration=5.0, slow_counts={})
    assert tripper(_ctx(metric, "closed")) is False

    # At threshold
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True

    # Above threshold
    metric = Metric(
        total_count=15, failure_count=8, total_duration=15.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True


def test_failure_rate():
    """FailureRate trips when failure ratio exceeds threshold."""
    tripper = FailureRate(ratio=0.5)

    # Below threshold (3/10 = 30%)
    metric = Metric(
        total_count=10, failure_count=3, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is False

    # At threshold (5/10 = 50%)
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True

    # Above threshold (7/10 = 70%)
    metric = Metric(
        total_count=10, failure_count=7, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True


def test_avg_latency():
    """AvgLatency trips when average duration reaches or exceeds threshold."""
    tripper = AvgLatency(threshold=1.0)

    # Below threshold (5.0 / 10 = 0.5s avg)
    metric = Metric(total_count=10, failure_count=0, total_duration=5.0, slow_counts={})
    assert tripper(_ctx(metric, "closed")) is False

    # At threshold (10.0 / 10 = 1.0s avg)
    metric = Metric(
        total_count=10, failure_count=0, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True

    # Above threshold (15.0 / 10 = 1.5s avg)
    metric = Metric(
        total_count=10, failure_count=0, total_duration=15.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True


def test_slow_call_rate():
    """SlowRate trips when slow call ratio for its threshold exceeds the ratio."""
    tripper = SlowRate(ratio=0.3, threshold=1.0)

    # Below threshold (2/10 = 20%)
    metric = Metric(
        total_count=10, failure_count=0, total_duration=10.0, slow_counts={1.0: 2}
    )
    assert tripper(_ctx(metric, "closed")) is False

    # At threshold (3/10 = 30%)
    metric = Metric(
        total_count=10, failure_count=0, total_duration=10.0, slow_counts={1.0: 3}
    )
    assert tripper(_ctx(metric, "closed")) is True

    # Above threshold (5/10 = 50%)
    metric = Metric(
        total_count=10, failure_count=0, total_duration=10.0, slow_counts={1.0: 5}
    )
    assert tripper(_ctx(metric, "closed")) is True


def test_slow_call_rate_picks_own_threshold():
    """Two SlowRate instances read independent counters keyed by their own threshold."""
    fast = SlowRate(ratio=0.3, threshold=1.0)
    slow = SlowRate(ratio=0.3, threshold=5.0)

    # 4/10 are >= 1.0, 1/10 is >= 5.0
    metric = Metric(
        total_count=10,
        failure_count=0,
        total_duration=10.0,
        slow_counts={1.0: 4, 5.0: 1},
    )
    assert fast(_ctx(metric, "closed")) is True  # 40% >= 30%
    assert slow(_ctx(metric, "closed")) is False  # 10% < 30%


def test_and_operator():
    """AND operator requires all conditions to be true."""
    # Common pattern: MinRequests & FailureRate
    tripper = MinRequests(10) & FailureRate(0.5)

    # Fails MinRequests (5 < 10)
    metric = Metric(total_count=5, failure_count=3, total_duration=5.0, slow_counts={})
    assert tripper(_ctx(metric, "closed")) is False

    # Passes MinRequests but fails FailureRate (3/10 = 30% < 50%)
    metric = Metric(
        total_count=10, failure_count=3, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is False

    # Passes both (10 >= 10 and 5/10 = 50%)
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed")) is True


def test_or_operator():
    """OR operator succeeds if any condition is true."""
    # Trip if either failure rate or slow call rate is high
    tripper = FailureRate(0.5) | SlowRate(0.3, threshold=1.0)

    # Neither condition met
    metric = Metric(
        total_count=10, failure_count=2, total_duration=10.0, slow_counts={1.0: 1}
    )
    assert tripper(_ctx(metric, "closed")) is False

    # Only FailureRate met (5/10 = 50%)
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={1.0: 1}
    )
    assert tripper(_ctx(metric, "closed")) is True

    # Only SlowRate met (3/10 = 30%)
    metric = Metric(
        total_count=10, failure_count=2, total_duration=10.0, slow_counts={1.0: 3}
    )
    assert tripper(_ctx(metric, "closed")) is True

    # Both met
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={1.0: 3}
    )
    assert tripper(_ctx(metric, "closed")) is True


def test_trippers_with_empty_metrics():
    """Trippers handle empty metrics (total_count=0) correctly."""
    empty_metric = Metric.empty()

    # MinRequests should fail
    assert MinRequests(10)(_ctx(empty_metric, "closed")) is False

    # Ratio-based trippers should not trip on empty metrics
    assert FailureRate(0.5)(_ctx(empty_metric, "closed")) is False
    assert AvgLatency(1.0)(_ctx(empty_metric, "closed")) is False
    assert SlowRate(0.3, threshold=1.0)(_ctx(empty_metric, "closed")) is False


def test_nested_logical_operators():
    """Logical operators can be nested (AND of AND, OR of OR)."""
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )

    # (A & B) & C - all three must pass
    tripper = (MinRequests(5) & FailureRate(0.5)) & MinRequests(10)
    assert tripper(_ctx(metric, "closed")) is True

    # (A | B) | C - any one must pass
    tripper = (MinRequests(20) | FailureRate(0.5)) | MinRequests(5)
    assert tripper(_ctx(metric, "closed")) is True


def test_mixed_logical_operators():
    """Mixed AND/OR operators can be combined."""
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )

    # (A & B) | C - either (A and B) or C
    tripper = (MinRequests(5) & FailureRate(0.5)) | MinRequests(20)
    assert tripper(_ctx(metric, "closed")) is True

    # (A | B) & C - (A or B) and C
    tripper = (MinRequests(20) | FailureRate(0.5)) & MinRequests(10)
    assert tripper(_ctx(metric, "closed")) is True


def test_failure_streak_invalid_count():
    """FailureStreak rejects invalid count."""
    with pytest.raises(ValueError, match="Count must be greater than zero"):
        FailureStreak(count=0)

    with pytest.raises(ValueError, match="Count must be greater than zero"):
        FailureStreak(count=-5)


def test_failure_streak():
    """FailureStreak trips when consecutive failure count reaches threshold."""
    tripper = FailureStreak(count=5)
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )

    # Below threshold
    assert tripper(_ctx(metric, "closed", consecutive_failures=3)) is False

    # At threshold
    assert tripper(_ctx(metric, "closed", consecutive_failures=5)) is True

    # Above threshold
    assert tripper(_ctx(metric, "closed", consecutive_failures=7)) is True


def test_failure_streak_with_or():
    """FailureStreak can be combined with OR for fast failure detection."""
    # Trip on 5 consecutive failures OR (20 requests with 50% failure rate)
    tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))
    metric = Metric(
        total_count=10, failure_count=5, total_duration=10.0, slow_counts={}
    )

    # Neither condition met
    assert tripper(_ctx(metric, "closed", consecutive_failures=3)) is False

    # Only ConsecutiveFailures met (fast path)
    assert tripper(_ctx(metric, "closed", consecutive_failures=5)) is True

    # Only MinRequests & FailureRate met
    metric = Metric(
        total_count=20, failure_count=10, total_duration=20.0, slow_counts={}
    )
    assert tripper(_ctx(metric, "closed", consecutive_failures=2)) is True


def test_tripper_leaf_iter_yields_self():
    """A leaf tripper iterates as a single-element sequence containing itself."""
    sr = SlowRate(0.3, threshold=1.0)
    assert list(sr) == [sr]


def test_tripper_composite_iter_yields_leaves_dfs():
    """Composite trippers iterate over their leaves in DFS order."""
    a = SlowRate(0.3, threshold=1.0)
    b = SlowRate(0.1, threshold=5.0)
    c = FailureRate(0.5)
    tripper = (a | b) & c
    assert list(tripper) == [a, b, c]
