from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from fluxgate.interfaces import IWindow
from fluxgate.metric import Record, Metric

__all__ = ["CountWindow", "TimeWindow"]


class CountWindow(IWindow):
    """Count-based sliding window for tracking recent call metrics.

    Maintains a fixed-size sliding window that keeps the most recent N calls.
    When the window is full, the oldest record is evicted when a new one arrives.

    Examples:
        >>> window = CountWindow(size=100)  # Track last 100 calls
        >>>
        >>> window.record(Record(success=True, duration=0.5))
        >>>
        >>> metric = window.get_metric()
        >>> print(metric.total_count)
        1

    Args:
        size: Maximum number of calls to track in the window
    """

    def __init__(self, size: int) -> None:
        self._max_size = size
        self._records: deque[Record] = deque(maxlen=size)
        self._total_count = 0
        self._total_failure_count = 0
        self._total_duration = 0.0
        self._slow_call_count = 0

    def record(self, record: Record) -> None:
        """Add a call record to the window.

        If window is full, evicts the oldest record before adding the new one.

        Args:
            record: Call result to record
        """
        if len(self._records) == self._max_size:
            evicted = self._records.popleft()
            self._evict(evicted)
        self._admit(record)

    def _admit(self, record: Record) -> None:
        self._records.append(record)
        self._total_count += 1
        self._total_duration += record.duration
        self._total_failure_count += 1 if not record.success else 0
        self._slow_call_count += 1 if record.is_slow else 0

    def _evict(self, evicted: Record) -> None:
        self._total_count -= 1
        self._total_failure_count -= 1 if not evicted.success else 0
        self._total_duration -= evicted.duration
        self._slow_call_count -= 1 if evicted.is_slow else 0

    def get_metric(self) -> Metric:
        """Get aggregated metrics for all records in the window.

        Returns:
            Aggregated metrics (counts, durations)
        """
        return Metric(
            total_count=self._total_count,
            failure_count=self._total_failure_count,
            total_duration=self._total_duration,
            slow_count=self._slow_call_count,
        )

    def reset(self) -> None:
        """Clear all records and reset metrics to zero."""
        self._records.clear()
        self._total_count = 0
        self._total_failure_count = 0
        self._total_duration = 0.0
        self._slow_call_count = 0


class TimeWindow(IWindow):
    """Time-based sliding window for tracking metrics over a time period.

    Divides time into fixed buckets (1 second each) and tracks metrics per bucket.
    When a bucket's time period expires, it is reset and reused for the new time.

    Examples:
        >>> window = TimeWindow(size=60)  # Track last 60 seconds
        >>>
        >>> window.record(Record(success=True, duration=0.5))
        >>>
        >>> metric = window.get_metric()

    Args:
        size: Number of seconds to track (window size in seconds)

    Note:
        Time precision is 1 second. All calls within the same second
        are grouped into the same bucket.
    """

    @dataclass
    class Bucket:
        sec_count: int = field(default=0)
        sec_failure_count: int = field(default=0)
        sec_total_duration: float = field(default=0.0)
        sec_slow_call_count: int = field(default=0)

        def admit(self, record: Record) -> None:
            self.sec_count += 1
            self.sec_failure_count += 1 if not record.success else 0
            self.sec_total_duration += record.duration
            self.sec_slow_call_count += 1 if record.is_slow else 0

        def reset(self) -> None:
            self.sec_count = 0
            self.sec_failure_count = 0
            self.sec_total_duration = 0.0
            self.sec_slow_call_count = 0

    def __init__(self, size: int) -> None:
        self._size = size
        self._buckets = [self.Bucket() for _ in range(size)]
        self._timestamps = [0 for _ in range(size)]
        self._total_count = 0
        self._total_failure_count = 0
        self._total_duration = 0.0
        self._slow_call_count = 0

    def _admit(self, record: Record, bucket: Bucket) -> None:
        self._total_count += 1
        self._total_failure_count += 1 if not record.success else 0
        self._total_duration += record.duration
        self._slow_call_count += 1 if record.is_slow else 0
        bucket.admit(record)

    def _evict(self, evicted: Bucket) -> None:
        self._total_count -= evicted.sec_count
        self._total_failure_count -= evicted.sec_failure_count
        self._total_duration -= evicted.sec_total_duration
        self._slow_call_count -= evicted.sec_slow_call_count
        evicted.reset()

    def record(self, record: Record) -> None:
        now = int(record.timestamp)
        index = now % self._size
        bucket = self._buckets[index]

        if self._timestamps[index] != now:
            evicted = self._buckets[index]
            self._evict(evicted)
            self._timestamps[index] = now

        self._admit(record, bucket)

    def get_metric(self) -> Metric:
        return Metric(
            total_count=self._total_count,
            failure_count=self._total_failure_count,
            total_duration=self._total_duration,
            slow_count=self._slow_call_count,
        )

    def reset(self) -> None:
        for bucket in self._buckets:
            bucket.reset()
        self._timestamps = [0 for _ in range(self._size)]
        self._total_count = 0
        self._total_failure_count = 0
        self._total_duration = 0.0
        self._slow_call_count = 0
