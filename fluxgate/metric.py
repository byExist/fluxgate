from dataclasses import dataclass, field
import time


@dataclass(frozen=True, slots=True, kw_only=True)
class Record:
    success: bool
    duration: float = field(default=0.0)
    is_slow: bool = field(default=False)
    timestamp: float = field(init=False, default_factory=time.time)


@dataclass(frozen=True, slots=True, kw_only=True)
class Metric:
    total_count: int
    total_duration: float
    failure_count: int
    slow_count: int

    @property
    def avg_duration(self) -> float | None:
        """Average duration per call. Returns None if no calls recorded."""
        return self.total_duration / self.total_count if self.total_count > 0 else None

    @property
    def failure_rate(self) -> float | None:
        """Failure rate (0.0 to 1.0). Returns None if no calls recorded."""
        return self.failure_count / self.total_count if self.total_count > 0 else None

    @property
    def slow_rate(self) -> float | None:
        """Slow call rate (0.0 to 1.0). Returns None if no calls recorded."""
        return self.slow_count / self.total_count if self.total_count > 0 else None
