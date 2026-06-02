# Changelog

All notable changes to this project will be documented in this file.

## [0.9.3] - 2026.06.02

### Fixed

- **Tripper now evaluated on the success path in `CLOSED`**. `_Closed.execute` previously evaluated the tripper only inside its `except` branch, so trippers that monitor metrics accumulating on successful calls (`SlowRate`, `AvgLatency`) never tripped a "successful but slow" workload even when the threshold was clearly exceeded. Evaluation now fires after every record, success or failure, in both the sync and async breakers; the async variant preserves the existing lock+signal+notify pattern. The two branches were collapsed into one by capturing the call outcome as a `tuple[R, float] | Exception` union and dispatching on `isinstance`.
- **Synchronous `CircuitBreaker` no longer silently drops async listeners**. `Listener` and `AsyncListener` are `runtime_checkable` Protocols differentiated only by the syntactic async-ness of `__call__`, which `runtime_checkable` does not inspect — so a coroutine-returning callable was accepted by a sync breaker, invoked without `await`, and the notification was discarded with a `RuntimeWarning` invisible in most production logging setups. The sync `_notify` now mirrors the existing guard in `AsyncCircuitBreaker._notify`: a returned coroutine is closed cleanly and an explicit `ERROR`-level log is emitted, while other listeners in the same notification continue to fire.

### Changed

- **Default permit changed to `RampUp(0.1, 1.0, 60.0)`** (previously `RampUp(0.0, 1.0, 60.0)`). With `initial=0.0` the computed ratio at HALF_OPEN entry was 0, so `random() < 0` denied every probe until the ramp progressed — effectively blocking traffic for ~60s after every cooldown, on top of the `Cooldown` itself. The new default admits ~10% of probes immediately.

### Breaking Changes

- **`RampUp(initial=0.0, ...)` now raises `ValueError`**. The value never made sense for HALF_OPEN admission (see above) and any breaker still constructing one was silently locking itself out. Migration: pass any small positive `initial` such as `0.1`, matching the new default.

## [0.9.2] - 2026.06.02

### Changed

- **`AsyncCircuitBreaker` consolidated to a single `_lock`**. The two locks introduced in 0.9.0 (`_state_lock` + `_window_lock`) merged into one, and the nested locking pattern is gone. Critical sections now hold synchronous code only. Public API and observable behaviour are unchanged.
- **Listener notifications moved outside the lock**. `_transition_to` returns a `Signal` for the caller to notify after releasing `_lock`, so a slow listener can no longer stall other calls or deadlock by re-entering the breaker.
- **State freshness guard switched from `from_state` strings to handler identity**. The three `_try_transition_to_*` helpers are gone; each handler now checks `cb._state is not self` under `_lock` to discard stale outcomes. Equivalent protection against the normal trip race. A regression back to the same handler instance (e.g. `closed → open → half_open → closed`) may still let one stale sample land in the freshly reset window — pair small windows with `MinRequests` if that could flip your tripper.
- **`_transition_to` is now synchronous and returns a `Signal`**. Callers hold `_lock`, transition, release, then `_notify`. Locking responsibility stays at the call site.
- **Explicit-command entry points unified into `_command`**. `reset/disable/metrics_only/force_open` delegate to a single helper instead of each duplicating the `lock → transition → notify` pattern.
- **`_HalfOpen` re-entry check uses `is self`** instead of `self.cb._state.state != "half_open"` — object identity over string comparison.
- **New concurrency tests** cover the trip race, slow listener, in-flight `disable()`, and stale-outcome containment.

## [0.9.1] - 2026.06.01

### Changed

- **`Metric` is now a monoid; `_Aggregator` removed**. The cumulative-counter dataclass introduced in 0.9.0 is gone — `Metric` gained `empty()`, `from_record()`, `__add__`, and `__sub__`, and `CountWindow`/`TimeWindow` keep a running `Metric` updated via these operators on every `record()`. The two-class indirection (mutable `_Aggregator` mirror of immutable `Metric`) collapses into one. Public `Window`/`Metric` API is unchanged.
- **`TimeWindow.__init__` delegates to `reset()`**, and **`CountWindow._max_size` is replaced by `self._records.maxlen`** — both eliminate state-init duplication.
- **Test fixture for empty `Metric` uses `Metric.empty()`** instead of a hand-rolled `Metric(...)` literal, so adding a field to `Metric` won't silently bypass empty-metric coverage in `test_trippers_with_empty_metrics`.

## [0.9.0] - 2026.05.31

### Changed

- **Slack listeners share a private base class (`_SlackBase`)**. `SlackListener` and `AsyncSlackListener` no longer duplicate template lookup, payload construction, and thread-tracking logic line-by-line; only the HTTP client and `__call__` differ. As a side effect, both classes now read defaults from the shared base, so overriding `TRANSITION_TEMPLATES` on `SlackListener` no longer leaks into `AsyncSlackListener` (which was an accident of the previous direct reference).
- **Window cumulative counters consolidated into `_Aggregator`**. The five-counter accumulation pattern (`total_count`, `total_failure_count`, `total_duration`, `slow_counts`) previously lived in three places — `CountWindow._admit`, `TimeWindow._admit`, and `TimeWindow.Bucket.admit`. They now live in one dataclass with `add`/`remove`/`subtract`/`reset`/`to_metric` methods. Adding a new aggregate metric (e.g. p99 latency) is now a single-site change. Public window API is unchanged.
- **State handlers reused via a `_handlers` dict**. Each breaker now builds one instance per `State` value at construction time and looks up `self._handlers[state]` in `_transition_to`. The six-branch `if/elif/else` ladder is gone — previously the final case (`forced_open`) sat in an unguarded `else`, silently catching anything it didn't recognise; the new dict lookup raises `KeyError` instead, so adding a `State` value without registering its handler fails loudly. Handlers carry only a reference to the parent breaker, so reusing one instance per state across transitions is safe.
- **State `execute` methods use `_record_success` / `_record_failure` helpers**. The `Record(success=..., duration=..., slow_at=_classify_slow(...))` + counter-update boilerplate previously appeared six times across `_Closed`, `_HalfOpen`, `_MetricsOnly` (sync and async). Centralising it makes what each state actually decides — tripper checks, transitions, no-op — visible at a glance. In the async breaker the helpers require the caller to hold `_window_lock`, keeping locking responsibility at the call site.
- **`Listener` and `AsyncListener` are now `runtime_checkable` Protocols** (previously ABCs). A listener can now be any callable matching the protocol — plain functions, lambdas, or bound methods all satisfy `Listener`/`AsyncListener` without inheriting. Existing `class MyListener(Listener): ...` patterns continue to work via structural typing.

### Breaking Changes

- **`StateEnum` enum replaced with `State` Literal alias** (`fluxgate.State`). State values were always just six fixed strings with no behaviour attached — a Literal expresses that more honestly and removes the constant `.value` noise. Affects `CircuitBreakerInfo.state`, `Signal.old_state`/`new_state`, `CallContext.state`, and any user code that compares state values. Migration: replace `StateEnum.OPEN` with `"open"`, `StateEnum.CLOSED` with `"closed"`, etc. (full set: `"closed"`, `"open"`, `"half_open"`, `"metrics_only"`, `"disabled"`, `"forced_open"`). To iterate all valid states, use `typing.get_args(State)` instead of iterating the enum.
- **`CallNotPermittedError.message` attribute removed**. The message was stored twice (in `args[0]` via `super().__init__` and again as `self.message`). Use `str(err)` or `err.args[0]` to read the message — the standard Python convention since PEP 352.
- **`Tripper.__call__` signature changed to a single `CallContext` argument**. The previous `(metric, state, consecutive_failures)` triple is replaced by `(ctx: CallContext)`, where `CallContext` is a frozen dataclass exposing `.metric`, `.state`, and `.consecutive_failures`. Only `FailureStreak` actually used `consecutive_failures`, so the previous signature forced every other tripper to declare an unused parameter. Future additions to the breaker's per-call state can be added to `CallContext` without changing the signature again.

**Migration (`Tripper.__call__`):**

```python
# Before (v0.8.x)
from fluxgate.trippers import Tripper
from fluxgate.metric import Metric
from fluxgate.state import StateEnum

class MyTripper(Tripper):
    def __call__(
        self, metric: Metric, state: StateEnum, consecutive_failures: int
    ) -> bool:
        return metric.failure_count > 10

# After (v0.9.0)
from fluxgate.trippers import CallContext, Tripper

class MyTripper(Tripper):
    def __call__(self, ctx: CallContext) -> bool:
        return ctx.metric.failure_count > 10
```

## [0.8.0] - 2026.05.28

### Breaking Changes

- **`name` parameter removed from `CircuitBreaker` and `AsyncCircuitBreaker`**. The circuit breaker is now anonymous — its identity is determined by where it's attached, not by a string. Identification for monitoring is the listener's responsibility.
- **`Signal.circuit_name` field removed**. `Signal` now carries only `old_state`, `new_state`, and `timestamp`.
- **`CircuitBreakerInfo.name` field removed**. Use the variable name or surrounding context to identify the breaker when inspecting `cb.info()`.
- **Listeners require a `name` parameter**: `LogListener`, `PrometheusListener`, `SlackListener`, and `AsyncSlackListener` all take `name` as their first argument. The name is used as a log prefix, a Prometheus label, or the identifier shown in Slack messages.
- **`SlackListener._open_threads` simplified**: a listener now tracks a single open thread instead of a per-circuit dictionary, since one instance is intended for one circuit.

**Migration:**

```python
# Before (v0.7.x)
cb = CircuitBreaker(
    name="payment_api",
    tripper=MinRequests(20) & FailureRate(0.5),
    listeners=[
        LogListener(),
        PrometheusListener(),
        SlackListener(channel="C123", token="xoxb-..."),
    ],
)

# After (v0.8.0)
cb = CircuitBreaker(
    tripper=MinRequests(20) & FailureRate(0.5),
    listeners=[
        LogListener(name="payment_api"),
        PrometheusListener(name="payment_api"),
        SlackListener(name="payment_api", channel="C123", token="xoxb-..."),
    ],
)
```

To attach a single `PrometheusListener` to many circuits as before, create one instance per circuit — the module-level Gauge/Counter still aggregates via the `circuit_name` label.

Custom listeners that previously read `signal.circuit_name` should accept `name` in their `__init__` and use `self._name`.

## [0.7.0] - 2026.05.28

### Breaking Changes

- **`SlowRate` now owns its threshold**: `SlowRate(ratio)` is replaced by `SlowRate(ratio, threshold)`. The "slow" duration is no longer a global property of the breaker; each `SlowRate` instance declares the threshold it cares about, so several can coexist with different thresholds.
- **`slow_threshold` parameter removed** from `CircuitBreaker` and `AsyncCircuitBreaker`. Move the value into each `SlowRate` instance.
- **Default tripper no longer includes `SlowRate`**: The default became `MinRequests(100) & FailureRate(0.5)`. Previously the default tripper included `SlowRate(1.0)` paired with `slow_threshold=60.0`, which was effectively disabled (it required 100% of calls to exceed 60s). If you want slow-call detection, add `SlowRate(ratio, threshold=...)` explicitly.
- **`Metric.slow_count: int` replaced by `slow_counts: Mapping[float, int]`** (per-threshold counters). The previous `Metric.slow_rate` property is now the method `Metric.slow_rate(threshold)`.
- **`Record.is_slow` removed; `Record.slow_at: tuple[float, ...]` added**: each record carries the set of thresholds it exceeded (computed by the producer, typically the circuit breaker on the call hot path). Windows simply aggregate counters keyed by these values.
- Slow-call classification now uses `>=` (a duration equal to the threshold counts as slow). The previous `slow_threshold` parameter used `>`.
- **Component interfaces are now abstract base classes (`abc.ABC`)**: `fluxgate.interfaces` is removed. `IWindow`, `ITracker`, `ITripper`, `IRetry`, `IPermit`, `IListener`, `IAsyncListener` Protocols are replaced by ABCs `Window`, `Tracker`, `Tripper`, `Retry`, `Permit`, `Listener`, `AsyncListener` defined in their respective modules (`fluxgate.windows`, `fluxgate.trackers`, ..., `fluxgate.listeners`). The `TripperBase`/`TrackerBase`/`RetryBase` helpers are gone; their names became the base classes themselves. Instantiating an ABC directly raises `TypeError` immediately, so misuse (`CircuitBreaker(retry=Retry())`) fails fast at construction time instead of on the first call.
- **`Tripper` is iterable**: composite trippers (`_And`/`_Or`) yield from their children, leaves yield themselves. The circuit breaker uses this to discover `SlowRate` thresholds inside the tripper tree.

**Migration:**

```python
# Before (v0.6.x)
from fluxgate.interfaces import IListener
class MyListener(IListener):
    def __call__(self, signal): ...

cb = CircuitBreaker(
    name="api",
    tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3)),
    slow_threshold=1.0,
)

# After (v0.7.0)
from fluxgate.listeners import Listener
class MyListener(Listener):
    def __call__(self, signal): ...

cb = CircuitBreaker(
    name="api",
    tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3, threshold=1.0)),
)
```

Custom `Window` implementations need no new methods. To support `SlowRate`, aggregate `record.slow_at` into per-threshold counters in your `record()` and surface them on `Metric.slow_counts`.

## [0.6.1] - 2026.05.27

### Fixed

- **`AsyncCircuitBreaker._notify`**: Async listeners implemented as callable classes (with `async def __call__`) are now properly awaited. Previously, `inspect.iscoroutinefunction` returned `False` for class instances, causing the returned coroutine to be silently dropped. ([#1](https://github.com/byExist/fluxgate/issues/1))

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
