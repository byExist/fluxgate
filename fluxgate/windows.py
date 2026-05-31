from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field

from fluxgate.metric import Record, Metric

__all__ = ["Window", "CountWindow", "TimeWindow"]


def _empty_slow_counts() -> dict[float, int]:
    return {}


@dataclass
class _Aggregator:
    """Running counts derived from admitted records.

    Centralises the cumulative metric state shared by both window types.
    Adding a new aggregate (e.g. p99 latency) means extending this one
    dataclass instead of touching every window's admit/evict path.
    """

    total_count: int = 0
    total_failure_count: int = 0
    total_duration: float = 0.0
    slow_counts: dict[float, int] = field(default_factory=_empty_slow_counts)

    def add(self, record: Record) -> None:
        self.total_count += 1
        self.total_failure_count += 0 if record.success else 1
        self.total_duration += record.duration
        for t in record.slow_at:
            self.slow_counts[t] = self.slow_counts.get(t, 0) + 1

    def remove(self, record: Record) -> None:
        self.total_count -= 1
        self.total_failure_count -= 0 if record.success else 1
        self.total_duration -= record.duration
        for t in record.slow_at:
            self.slow_counts[t] -= 1

    def subtract(self, other: "_Aggregator") -> None:
        """Subtract another aggregator's counts (used when a bucket expires)."""
        self.total_count -= other.total_count
        self.total_failure_count -= other.total_failure_count
        self.total_duration -= other.total_duration
        for t, count in other.slow_counts.items():
            self.slow_counts[t] -= count

    def reset(self) -> None:
        self.total_count = 0
        self.total_failure_count = 0
        self.total_duration = 0.0
        self.slow_counts.clear()

    def to_metric(self) -> Metric:
        return Metric(
            total_count=self.total_count,
            failure_count=self.total_failure_count,
            total_duration=self.total_duration,
            slow_counts=dict(self.slow_counts),
        )


class Window(ABC):
    """Base class for sliding windows over recent call records.

    Subclasses must override ``record``, ``get_metric``, and ``reset``.
    """

    @abstractmethod
    def record(self, record: Record) -> None: ...

    @abstractmethod
    def get_metric(self) -> Metric: ...

    @abstractmethod
    def reset(self) -> None: ...


class CountWindow(Window):
    """Count-based sliding window for tracking recent call metrics.

    Maintains a fixed-size sliding window that keeps the most recent N calls.
    When the window is full, the oldest record is evicted when a new one arrives.

    Per-threshold slow-call counters are populated from `record.slow_at` — the
    set of thresholds the call exceeded, decided by the producer (typically
    the circuit breaker). The window itself does not need to know which
    thresholds are active.

    Examples:
        >>> window = CountWindow(size=100)
        >>> window.record(Record(success=True, duration=0.5, slow_at=()))
        >>> metric = window.get_metric()

    Args:
        size: Maximum number of calls to track in the window
    """

    def __init__(self, size: int) -> None:
        self._max_size = size
        self._records: deque[Record] = deque(maxlen=size)
        self._agg = _Aggregator()

    def record(self, record: Record) -> None:
        if len(self._records) == self._max_size:
            evicted = self._records.popleft()
            self._agg.remove(evicted)
        self._records.append(record)
        self._agg.add(record)

    def get_metric(self) -> Metric:
        return self._agg.to_metric()

    def reset(self) -> None:
        self._records.clear()
        self._agg.reset()


class TimeWindow(Window):
    """Time-based sliding window for tracking metrics over a time period.

    Divides time into fixed buckets (1 second each) and tracks metrics per bucket.
    When a bucket's time period expires, it is reset and reused for the new time.

    Per-threshold slow-call counters are populated from `record.slow_at`, just
    like `CountWindow`.

    Args:
        size: Number of seconds to track (window size in seconds)

    Note:
        Time precision is 1 second. All calls within the same second
        are grouped into the same bucket.
    """

    def __init__(self, size: int) -> None:
        self._size = size
        self._buckets: list[_Aggregator] = [_Aggregator() for _ in range(size)]
        self._timestamps = [0 for _ in range(size)]
        self._total = _Aggregator()

    def record(self, record: Record) -> None:
        now = int(record.timestamp)
        index = now % self._size
        bucket = self._buckets[index]

        if self._timestamps[index] != now:
            self._total.subtract(bucket)
            bucket.reset()
            self._timestamps[index] = now

        bucket.add(record)
        self._total.add(record)

    def get_metric(self) -> Metric:
        return self._total.to_metric()

    def reset(self) -> None:
        for bucket in self._buckets:
            bucket.reset()
        self._timestamps = [0 for _ in range(self._size)]
        self._total.reset()
