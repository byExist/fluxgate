from collections.abc import Mapping
from dataclasses import dataclass, field
import time


@dataclass(frozen=True, slots=True, kw_only=True)
class Record:
    success: bool
    duration: float = field(default=0.0)
    slow_at: tuple[float, ...] = field(default=())
    timestamp: float = field(init=False, default_factory=time.time)


@dataclass(frozen=True, slots=True, kw_only=True)
class Metric:
    total_count: int
    total_duration: float
    failure_count: int
    slow_counts: Mapping[float, int]

    @classmethod
    def empty(cls) -> "Metric":
        """Identity element of the metric monoid."""
        return cls(
            total_count=0,
            total_duration=0.0,
            failure_count=0,
            slow_counts={},
        )

    @classmethod
    def from_record(cls, record: Record) -> "Metric":
        """One record's contribution to a window's running metric."""
        return cls(
            total_count=1,
            total_duration=record.duration,
            failure_count=0 if record.success else 1,
            slow_counts={t: 1 for t in record.slow_at},
        )

    def __add__(self, other: "Metric") -> "Metric":
        merged: dict[float, int] = dict(self.slow_counts)
        for t, count in other.slow_counts.items():
            merged[t] = merged.get(t, 0) + count
        return Metric(
            total_count=self.total_count + other.total_count,
            total_duration=self.total_duration + other.total_duration,
            failure_count=self.failure_count + other.failure_count,
            slow_counts=merged,
        )

    def __sub__(self, other: "Metric") -> "Metric":
        merged: dict[float, int] = dict(self.slow_counts)
        for t, count in other.slow_counts.items():
            new_count = merged.get(t, 0) - count
            if new_count == 0:
                merged.pop(t, None)
            else:
                merged[t] = new_count
        return Metric(
            total_count=self.total_count - other.total_count,
            total_duration=self.total_duration - other.total_duration,
            failure_count=self.failure_count - other.failure_count,
            slow_counts=merged,
        )

    @property
    def avg_duration(self) -> float | None:
        """Average duration per call. Returns None if no calls recorded."""
        return self.total_duration / self.total_count if self.total_count > 0 else None

    @property
    def failure_rate(self) -> float | None:
        """Failure rate (0.0 to 1.0). Returns None if no calls recorded."""
        return self.failure_count / self.total_count if self.total_count > 0 else None

    def slow_rate(self, threshold: float) -> float | None:
        """Slow call rate (0.0 to 1.0) for the given threshold.

        Returns None if no calls recorded.
        """
        if self.total_count == 0:
            return None
        return self.slow_counts.get(threshold, 0) / self.total_count
