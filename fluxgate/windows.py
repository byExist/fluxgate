from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque

from fluxgate.metric import Record, Metric

__all__ = ["Window", "CountWindow", "TimeWindow"]


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
        self._records: deque[Record] = deque(maxlen=size)
        self._metric = Metric.empty()

    def record(self, record: Record) -> None:
        if len(self._records) == self._records.maxlen:
            evicted = self._records.popleft()
            self._metric = self._metric - Metric.from_record(evicted)
        self._records.append(record)
        self._metric = self._metric + Metric.from_record(record)

    def get_metric(self) -> Metric:
        return self._metric

    def reset(self) -> None:
        self._records.clear()
        self._metric = Metric.empty()


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
        self.reset()

    def record(self, record: Record) -> None:
        now = int(record.timestamp)
        index = now % self._size

        if self._timestamps[index] != now:
            self._total = self._total - self._buckets[index]
            self._buckets[index] = Metric.empty()
            self._timestamps[index] = now

        contribution = Metric.from_record(record)
        self._buckets[index] = self._buckets[index] + contribution
        self._total = self._total + contribution

    def get_metric(self) -> Metric:
        return self._total

    def reset(self) -> None:
        self._buckets = [Metric.empty() for _ in range(self._size)]
        self._timestamps = [0 for _ in range(self._size)]
        self._total = Metric.empty()
