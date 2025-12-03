# Fluxgate

A modern, composable circuit breaker library for Python with full support for both synchronous and asynchronous code.

[![Python Version](https://img.shields.io/pypi/pyversions/fluxgate.svg)](https://pypi.org/project/fluxgate/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- **Sync & Async**: First-class support for both synchronous and asynchronous code
- **Composable**: Build complex failure detection logic using simple, reusable components
- **Multiple Window Types**: Count-based and time-based sliding windows
- **Flexible Failure Detection**: Combine multiple conditions with logical operators
- **Zero Dependencies**: Core library has no external dependencies
- **Built-in Monitoring**: Optional Prometheus, Slack, and logging integrations
- **Fully Typed**: Complete type hints for better IDE support

## Installation

```bash
pip install fluxgate

# Optional integrations
pip install fluxgate[prometheus]  # Prometheus metrics
pip install fluxgate[slack]       # Slack notifications
pip install fluxgate[all]         # Everything
```

## Quick Start

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="payment_api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
    slow_threshold=float("inf"),
)

@cb
def call_payment_api(amount: float):
    return requests.post("https://api.example.com/pay", json={"amount": amount})
```

### Async Support

```python
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
    slow_threshold=float("inf"),
)

@cb
async def call_async_api():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com/data")
```

## Core Concepts

### States

```text
┌─────────┐           ┌──────┐
│ CLOSED  │──────────>│ OPEN │<─────┐
└─────────┘ [tripper] └──────┘      │
     ^                    │         │
     │                    │[retry]  │[tripper]
     │                    v         │
     │               ┌───────────┐  │
     └───────────────│ HALF_OPEN │──┘
        [!tripper]   └───────────┘
```

- **CLOSED**: Normal operation
- **OPEN**: Failure threshold exceeded, calls blocked
- **HALF_OPEN**: Testing recovery (permit controls which calls are allowed)

### Windows

Track call history over a sliding window:

- `CountWindow(size)` - Last N calls
- `TimeWindow(size)` - Last N seconds

### Components

| Component | Purpose | Available Implementations |
|-----------|---------|---------------------------|
| **Trackers** | Define what exceptions to track | `All()`, `TypeOf(*types)`, `Custom(func)` — composable: `&`, `\|`, `~` |
| **Trippers** | When to open the circuit | `Closed()`, `HalfOpened()`, `MinRequests(n)`, `FailureRate(ratio)`, `AvgLatency(sec)`, `SlowRate(ratio)` — composable: `&`, `\|` |
| **Retries** | When to retry from OPEN → HALF_OPEN | `Never()`, `Always()`, `Cooldown(duration, jitter_ratio=0.0)`, `Backoff(initial, multiplier=2.0, max_duration=300.0, jitter_ratio=0.0)` |
| **Permits** | Which calls allowed in HALF_OPEN | `Random(ratio)`, `RampUp(initial, final, duration)` |

## Monitoring

```python
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener
from fluxgate.listeners.slack import SlackListener

cb = CircuitBreaker(
    ...,
    listeners=[
        LogListener(),
        PrometheusListener(),
        SlackListener(channel="C1234567890", token="xoxb-..."),
    ]
)
```

## Manual Control

```python
# Get circuit state
info = cb.info()
print(f"State: {info.state}")
print(f"Failures: {info.metrics.failure_count}/{info.metrics.total_count}")

# Manual transitions
cb.disable()      # -> DISABLED (pass-through, no tracking)
cb.metrics_only() # -> METRICS_ONLY (pass-through, with tracking)
cb.force_open()   # -> FORCED_OPEN (block all calls)
cb.reset()        # -> CLOSED (clears metrics)
```

## Error Handling

```python
from fluxgate import CallNotPermittedError

try:
    result = cb.call(risky_function)
except CallNotPermittedError:
    result = get_cached_value()  # Fallback
```

## Production-Ready Example

External payment API with multi-process deployment:

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener

# Track only 5xx errors and network failures (not client errors like 4xx)
def is_retriable_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

payment_cb = CircuitBreaker(
    # Circuit breaker identifier for logging and metrics
    name="payment_api",

    # Track last 100 calls (more predictable than TimeWindow across processes)
    window=CountWindow(size=100),

    # Define which exceptions count as failures
    tracker=Custom(is_retriable_error),

    # When to open: CLOSED needs 20+ calls & 60% failure; HALF_OPEN trips at 50%
    tripper=MinRequests(20) & ((Closed() & FailureRate(0.6)) | (HalfOpened() & FailureRate(0.5))),

    # When to retry: exponential backoff 10s, 20s, 40s... up to 300s with ±10% jitter
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0, jitter_ratio=0.1),

    # Which calls allowed in HALF_OPEN: gradually ramp 10% → 50% over 60s
    permit=RampUp(initial=0.1, final=0.5, duration=60.0),

    # Mark calls slower than 3s as slow
    slow_threshold=3.0,

    # Event listeners for logging and metrics
    listeners=[LogListener(), PrometheusListener()],
)

@payment_cb
def charge_payment(amount: float):
    response = httpx.post("https://payment-api.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()
```

## Requirements

- Python 3.10+
- Optional: `prometheus-client` for Prometheus support
- Optional: `httpx` for Slack support

## License

MIT License

## Contributing

Contributions welcome! Please submit a Pull Request.
