# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2025.12.05

### Breaking Changes

- **`ITripper` interface signature changed**: The `__call__` method now accepts an optional `consecutive_failures` parameter. Custom tripper implementations must update their signature:

```python
# Before (v0.2.x)
def __call__(self, metric: Metric, state: StateEnum) -> bool: ...

# After (v0.3.0)
def __call__(self, metric: Metric, state: StateEnum, consecutive_failures: int = 0) -> bool: ...
```

### Added

- **`FailureStreak` tripper**: Trip the circuit after N consecutive failures. Useful for fast failure detection during cold start or complete service outage.

```python
from fluxgate.trippers import FailureStreak, MinRequests, FailureRate

# Fast trip on 5 consecutive failures, or statistical trip on 50% failure rate
tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))
```

## [0.2.0] - 2025.12.03

### Breaking Changes

- **`slow_threshold` is now required**: The `slow_threshold` parameter no longer has a default value and must be explicitly set when creating `CircuitBreaker` or `AsyncCircuitBreaker` instances.
    - If you don't use `SlowRate`, set it to `float("inf")` to disable slow call tracking.
    - This follows Python's principle: "Explicit is better than implicit."

**Migration:**

<!--pytest.mark.skip-->

```python
# Before (v0.1.x)
cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    ...
)

# After (v0.2.0)
cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    ...
    slow_threshold=float("inf"),  # or a specific value like 3.0
)
```

## [0.1.2] - 2025.12.03

### Changed

- **LogListener**: Added `logger` and `level_map` parameters for flexible logging configuration.
    - `logger`: Inject a custom logger instance instead of using the root logger.
    - `level_map`: Customize log levels per state (default: `OPEN`/`FORCED_OPEN` → `WARNING`, others → `INFO`).

## [0.1.1] - 2025.12.01

This is the initial public release of Fluxgate.

### Features

- ✨ **Core**: Initial implementation of `CircuitBreaker` and `AsyncCircuitBreaker`.
- ✨ **Windows**: Sliding window strategies (`CountWindow`, `TimeWindow`).
- ✨ **Trackers**: Composable failure trackers (`All`, `TypeOf`, `Custom`) with `&`, `|`, and `~` operators.
- ✨ **Trippers**: Composable tripping conditions (`Closed`, `HalfOpened`, `MinRequests`, `FailureRate`, `AvgLatency`, `SlowRate`) with `&` and `|` operators.
- ✨ **Retries**: Recovery strategies (`Never`, `Always`, `Cooldown`, `Backoff`).
- ✨ **Permits**: Gradual recovery strategies (`Random`, `RampUp`).
- ✨ **Listeners**: Built-in monitoring and alerting integrations (`LogListener`, `PrometheusListener`, `SlackListener`).
- ✨ **Manual Control**: Methods for manual intervention (`disable`, `metrics_only`, `force_open`, `reset`).
- ✨ **Typing**: Full type hinting and `py.typed` compliance for excellent IDE support.
