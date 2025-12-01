"""Tests for window implementations (CountWindow, TimeWindow)."""

from math import isclose

from fluxgate.windows import CountWindow, TimeWindow
from fluxgate.metric import Record


def test_count_window_records_and_aggregates():
    """Records are added and metrics aggregated correctly."""
    window = CountWindow(size=5)

    window.record(Record(success=True, duration=0.5))
    window.record(Record(success=False, duration=1.0))
    window.record(Record(success=True, duration=0.3))

    metric = window.get_metric()
    assert metric.total_count == 3
    assert metric.failure_count == 1
    assert isclose(metric.total_duration, 1.8)


def test_count_window_fifo_eviction():
    """Oldest record is evicted when window is full (FIFO)."""
    window = CountWindow(size=3)

    # Fill the window
    window.record(Record(success=False, duration=1.0))  # Will be evicted
    window.record(Record(success=True, duration=0.5))
    window.record(Record(success=True, duration=0.3))

    metric = window.get_metric()
    assert metric.total_count == 3
    assert metric.failure_count == 1

    # Add one more - should evict the first failure
    window.record(Record(success=True, duration=0.2))

    metric = window.get_metric()
    assert metric.total_count == 3
    assert metric.failure_count == 0  # First failure evicted
    assert isclose(metric.total_duration, 1.0)


def test_count_window_slow_call_tracking():
    """Slow calls are tracked and evicted correctly."""
    window = CountWindow(size=3)

    window.record(Record(success=True, duration=2.0, is_slow=True))  # Will be evicted
    window.record(Record(success=True, duration=0.5, is_slow=False))
    window.record(Record(success=True, duration=3.5, is_slow=True))

    metric = window.get_metric()
    assert metric.total_count == 3
    assert metric.slow_count == 2

    # Evict the first slow call
    window.record(Record(success=True, duration=0.1, is_slow=False))

    metric = window.get_metric()
    assert metric.slow_count == 1


def test_count_window_reset():
    """Reset clears all records and metrics."""
    window = CountWindow(size=10)

    window.record(Record(success=True, duration=0.5))
    window.record(Record(success=False, duration=1.0))
    window.record(Record(success=True, duration=0.3, is_slow=True))

    window.reset()

    metric = window.get_metric()
    assert metric.total_count == 0
    assert metric.failure_count == 0
    assert metric.total_duration == 0.0
    assert metric.slow_count == 0


def test_count_window_size_one():
    """Window with size=1 keeps only the latest record."""
    window = CountWindow(size=1)

    window.record(Record(success=False, duration=1.0))
    metric = window.get_metric()
    assert metric.total_count == 1
    assert metric.failure_count == 1

    window.record(Record(success=True, duration=0.5))
    metric = window.get_metric()
    assert metric.total_count == 1
    assert metric.failure_count == 0
    assert isclose(metric.total_duration, 0.5)


def test_time_window_accumulates_records_in_same_second():
    """Multiple records in the same second are accumulated in same bucket."""
    window = TimeWindow(size=60)
    import time

    base_time = time.time()

    # All in the same second
    r1 = Record(success=True, duration=0.1)
    object.__setattr__(r1, "timestamp", base_time)
    window.record(r1)

    r2 = Record(success=True, duration=0.2)
    object.__setattr__(r2, "timestamp", base_time)
    window.record(r2)

    r3 = Record(success=False, duration=0.3)
    object.__setattr__(r3, "timestamp", base_time)
    window.record(r3)

    metric = window.get_metric()
    assert metric.total_count == 3
    assert metric.failure_count == 1
    assert isclose(metric.total_duration, 0.6)


def test_time_window_bucket_wraparound_eviction():
    """When bucket index wraps around, old data in that bucket is evicted."""
    window = TimeWindow(size=3)  # 3 buckets
    import time

    base_time = time.time()

    # Fill 3 buckets
    r1 = Record(success=False, duration=1.0)
    object.__setattr__(r1, "timestamp", base_time)
    window.record(r1)

    r2 = Record(success=True, duration=0.5)
    object.__setattr__(r2, "timestamp", base_time + 1)
    window.record(r2)

    r3 = Record(success=True, duration=0.3)
    object.__setattr__(r3, "timestamp", base_time + 2)
    window.record(r3)

    metric = window.get_metric()
    assert metric.total_count == 3
    assert metric.failure_count == 1

    # Wraparound: timestamp base_time+3 reuses bucket from base_time
    r4 = Record(success=True, duration=0.2, is_slow=True)
    object.__setattr__(r4, "timestamp", base_time + 3)
    window.record(r4)

    metric = window.get_metric()
    assert metric.total_count == 3  # r1 evicted, r2, r3, r4 remain
    assert metric.failure_count == 0  # r1's failure evicted
    assert metric.slow_count == 1  # r4's slow call tracked
    assert isclose(metric.total_duration, 1.0)


def test_time_window_bucket_reuse_across_time():
    """Same bucket can be reused multiple times as time progresses."""
    window = TimeWindow(size=5)
    import time

    base_time = time.time()

    # Multiple records in same bucket (same timestamp)
    r1 = Record(success=True, duration=0.1)
    object.__setattr__(r1, "timestamp", base_time)
    window.record(r1)

    r2 = Record(success=True, duration=0.2)
    object.__setattr__(r2, "timestamp", base_time)
    window.record(r2)

    metric = window.get_metric()
    assert metric.total_count == 2

    # Reuse same bucket index (base_time + 5)
    r3 = Record(success=False, duration=1.0)
    object.__setattr__(r3, "timestamp", base_time + 5)
    window.record(r3)

    metric = window.get_metric()
    assert metric.total_count == 1  # r1, r2 evicted
    assert metric.failure_count == 1
    assert isclose(metric.total_duration, 1.0)

    # Reuse again (base_time + 10)
    r4 = Record(success=True, duration=0.5)
    object.__setattr__(r4, "timestamp", base_time + 10)
    window.record(r4)

    r5 = Record(success=True, duration=0.3)
    object.__setattr__(r5, "timestamp", base_time + 10)
    window.record(r5)

    metric = window.get_metric()
    assert metric.total_count == 2  # Only r4, r5 remain
    assert metric.failure_count == 0
    assert isclose(metric.total_duration, 0.8)


def test_time_window_slow_call_tracking():
    """Slow calls are tracked correctly in time windows."""
    window = TimeWindow(size=60)
    import time

    base_time = time.time()

    r1 = Record(success=True, duration=0.5, is_slow=False)
    object.__setattr__(r1, "timestamp", base_time)
    window.record(r1)

    r2 = Record(success=True, duration=2.0, is_slow=True)
    object.__setattr__(r2, "timestamp", base_time)
    window.record(r2)

    r3 = Record(success=True, duration=3.5, is_slow=True)
    object.__setattr__(r3, "timestamp", base_time)
    window.record(r3)

    metric = window.get_metric()
    assert metric.slow_count == 2


def test_time_window_reset():
    """Reset clears all buckets and metrics."""
    window = TimeWindow(size=60)
    import time

    base_time = time.time()

    r1 = Record(success=True, duration=0.5)
    object.__setattr__(r1, "timestamp", base_time)
    window.record(r1)

    r2 = Record(success=False, duration=1.0)
    object.__setattr__(r2, "timestamp", base_time)
    window.record(r2)

    window.reset()

    metric = window.get_metric()
    assert metric.total_count == 0
    assert metric.failure_count == 0
    assert metric.total_duration == 0.0
    assert metric.slow_count == 0
