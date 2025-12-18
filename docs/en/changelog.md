# Changelog

All notable changes to this project will be documented in this file.

## [0.6.0] - 2025.12.18

### Breaking Changes

- **Removed `notify` parameter from manual control methods**: The `notify` parameter has been removed from `reset()`, `disable()`, `metrics_only()`, and `force_open()` methods. Listeners are now always notified on state transitions.

## [0.5.1] - 2025.12.17

### Fixed

- **SlackListener thread management**: Improved thread lifecycle for manual state transitions.
    - Thread now ends on transitions to `CLOSED`, `DISABLED`, or `METRICS_ONLY` (previously only `HALF_OPEN → CLOSED`)
    - Thread continues on transitions to `FORCED_OPEN` since the failure cycle persists
    - Direct `reset()` from `OPEN` now properly clears the thread for the next failure cycle

## [0.5.0] - 2025.12.16

### Added

- **`All` permit strategy**: A simple permit that always allows all calls in `HALF_OPEN` state. Useful for testing or when you want to rely solely on the tripper for state transitions.

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import All

cb = CircuitBreaker(name="api", permit=All())
```

- **`Template` TypedDict for SlackListener**: Customize Slack message templates by subclassing `SlackListener` and overriding `TRANSITION_TEMPLATES` and `FALLBACK_TEMPLATE` class attributes.

```python
from fluxgate.listeners.slack import SlackListener, Template
from fluxgate.state import StateEnum

class CustomSlackListener(SlackListener):
    TRANSITION_TEMPLATES: dict[tuple[StateEnum, StateEnum], Template] = {
        (StateEnum.CLOSED, StateEnum.OPEN): {
            "title": "🚨 Alert",
            "color": "#FF0000",
            "description": "Circuit opened!",
        },
    }
```

## [0.4.1] - 2025.12.15

### Added

- **Sensible defaults for CircuitBreaker**: All component parameters now have default values, allowing simpler initialization with just a name:

```python
from fluxgate import CircuitBreaker

cb = CircuitBreaker("my-service")

@cb
def call_api():
    return requests.get("https://api.example.com")
```

Default values:

- `window`: `CountWindow(100)`
- `tracker`: `All()`
- `tripper`: `MinRequests(100) & (FailureRate(0.5) | SlowRate(1.0))`
- `retry`: `Cooldown(60.0)`
- `permit`: `RampUp(0.0, 1.0, 60.0)`
- `slow_threshold`: `60.0`

## [0.4.0] - 2025.12.05

### Breaking Changes

- **`AvgLatency` now uses `>=` instead of `>`**: The tripper now trips when the average latency **reaches or exceeds** the threshold, consistent with other rate-based trippers (`FailureRate`, `SlowRate`).
- **`TypeOf` now requires at least one exception type**: Creating `TypeOf()` without arguments now raises `ValueError`.

### Fixed

- **`SlackListener` no longer crashes on unsupported transitions**: Previously, state transitions not in the predefined message templates (e.g., `DISABLED`, `FORCED_OPEN`, `METRICS_ONLY`, or manual `reset()` from `OPEN` to `CLOSED`) would raise `KeyError`. Now these transitions are silently ignored.

## [0.3.1] - 2025.12.05

### Breaking Changes

- **`ITripper.consecutive_failures` is now required**: The `consecutive_failures` parameter no longer has a default value. Custom tripper implementations must pass this argument explicitly.

## [0.3.0] - 2025.12.05

### Breaking Changes

- **`ITripper` interface signature changed**: The `__call__` method now accepts a `consecutive_failures` parameter. Custom tripper implementations must update their signature:

<!--pytest.mark.skip-->

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
