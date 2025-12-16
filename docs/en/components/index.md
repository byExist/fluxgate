# Components Overview

Fluxgate uses composable components to build flexible circuit breaker configurations. Each component handles a specific aspect of circuit breaker behavior.

## Architecture

| Component | Role | Operators |
|-----------|------|-----------|
| **Window** | Track call history (count or time-based) | - |
| **Tracker** | Define which exceptions to track | &, \|, ~ |
| **Tripper** | Decide when to open/close the circuit | &, \| |
| **Retry** | Control OPEN → HALF_OPEN transition | - |
| **Permit** | Control call admission in HALF_OPEN | - |
| **Listener** | Detect state transitions and notify external systems | - |

## Component Types

### [Windows](windows.md)

Track call history over a sliding window.

- **CountWindow** - Last N calls
- **TimeWindow** - Last N seconds

```python
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # Track last 100 calls
window = TimeWindow(size=60)    # Track last 60 seconds
```

### [Trackers](trackers.md)

Define which exceptions count as failures.

- **All** - Track all exceptions
- **TypeOf** - Track specific exception types
- **Custom** - Custom tracking logic

```python
from fluxgate.trackers import TypeOf, Custom

tracker = TypeOf(ConnectionError, TimeoutError)
tracker = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
```

**Composable**: Use `&`, `|`, `~` operators to combine trackers.

### [Trippers](trippers.md)

Determine when to open or close the circuit based on metrics.

- **Closed/HalfOpened** - State-based conditions
- **MinRequests** - Minimum call count
- **FailureRate** - Failure percentage
- **AvgLatency** - Average response time
- **SlowRate** - Slow call percentage

```python
from fluxgate.trippers import Closed, MinRequests, FailureRate

tripper = Closed() & MinRequests(10) & FailureRate(0.5)
```

**Composable**: Use `&`, `|` operators to combine conditions.

### [Retries](retries.md)

Control when to transition from OPEN to HALF_OPEN state.

- **Never** - Require manual reset
- **Always** - Immediate retry
- **Cooldown** - Fixed wait period
- **Backoff** - Exponential backoff

```python
from fluxgate.retries import Cooldown, Backoff

retry = Cooldown(duration=60.0, jitter_ratio=0.1)
retry = Backoff(initial=10.0, multiplier=2.0, max_duration=300.0)
```

### [Permits](permits.md)

Control which calls are allowed in HALF_OPEN state.

- **All** - Always allow (for testing)
- **Random** - Probabilistic admission
- **RampUp** - Gradual traffic increase

```python
from fluxgate.permits import All, Random, RampUp

permit = All()
permit = Random(ratio=0.5)
permit = RampUp(initial=0.1, final=0.8, duration=60.0)
```

### [Listeners](listeners/index.md)

Detect state transitions and notify external systems.

- **LogListener** - Standard logging
- **PrometheusListener** - Prometheus metrics (opt)
- **SlackListener** - Slack notifications (opt)

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.log import LogListener

listeners = [LogListener()]
cb = CircuitBreaker(..., listeners=listeners)
```

## Full Example

Putting it all together:

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import TimeWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import MinRequests, FailureRate, SlowRate
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=TimeWindow(size=60),  # Track calls from last 60 seconds
    tracker=TypeOf(ConnectionError, TimeoutError),
    tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.8)),
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0),
    permit=RampUp(initial=0.1, final=0.5, duration=60.0),
    slow_threshold=2.0,  # Calls over 2 seconds are considered slow
)
```

## Next Steps

Explore each component in detail:

- [Windows](windows.md) - Choose the right window type
- [Trackers](trackers.md) - Define failure criteria
- [Trippers](trippers.md) - Configure circuit behavior
- [Retries](retries.md) - Plan recovery strategy
- [Permits](permits.md) - Control traffic during recovery
- [Listeners](listeners/index.md) - Monitor state transitions
