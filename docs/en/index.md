# Fluxgate

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/byExist/fluxgate/blob/master/LICENSE)

A modern, composable circuit breaker library for Python with full support for both synchronous and asynchronous code.

## Why Fluxgate?

Circuit breakers prevent cascading failures in distributed systems by monitoring service health and temporarily blocking calls to failing services. Fluxgate makes this easy with:

- **Sync & Async**: First-class support for both synchronous and asynchronous code
- **Composable**: Build complex failure detection logic using simple, reusable components
- **Zero Dependencies**: Core library has no external dependencies
- **Fully Typed**: Complete type hints for better IDE support
- **Production Ready**: Built-in monitoring with Prometheus, Slack, and logging

## Quick Start

### Installation

```bash
pip install fluxgate
```

### Basic Example

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
)

@cb
def call_payment_api(amount: float):
    return requests.post("https://api.example.com/pay", json={"amount": amount})
```

### How It Works

The circuit breaker operates in three main states:

```text
CLOSED --[tripper]--> OPEN --[retry]--> HALF_OPEN --[!tripper]--> CLOSED
                       ^                   |
                       +----[tripper]------+
```

- **CLOSED**: Normal operation, all calls pass through
- **OPEN**: Failure threshold exceeded, calls are blocked
- **HALF_OPEN**: Testing recovery, limited calls allowed

## Core Components

Fluxgate uses composable components to build flexible failure detection logic:

| Component | Purpose | Examples |
|-----------|---------|----------|
| **Windows** | Track call history | `CountWindow(100)` - last 100 calls |
|  |  | `TimeWindow(60)` - last 60 seconds |
| **Trackers** | Define what to track | `TypeOf(ConnectionError)` - track specific errors |
|  |  | `Custom(func)` - custom logic |
| **Trippers** | When to open circuit | `FailureRate(0.5)` - 50% failure rate |
|  |  | `AvgLatency(2.0)` - slow responses |
| **Retries** | When to retry | `Cooldown(60.0)` - wait 60 seconds |
|  |  | `Backoff(10.0)` - exponential backoff |
| **Permits** | Control recovery | `Random(0.5)` - allow 50% of calls |
|  |  | `RampUp(0.1, 0.8, 60)` - gradual ramp |

## Async Support

Full support for asyncio applications:

```python
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
    max_half_open_calls=5,
)

@cb
async def call_async_api():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com/data")
```

## Production Example

A production-ready circuit breaker for an external payment API:

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

# Track only 5xx errors and network failures
def is_retriable_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

payment_cb = CircuitBreaker(
    name="payment_api",
    window=CountWindow(size=100),
    tracker=Custom(is_retriable_error),
    tripper=MinRequests(20) & (
        (Closed() & FailureRate(0.6)) |
        (HalfOpened() & FailureRate(0.5))
    ),
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0, jitter_ratio=0.1),
    permit=RampUp(initial=0.1, final=0.5, duration=60.0),
    listeners=[LogListener(), PrometheusListener()],
)

@payment_cb
def charge_payment(amount: float):
    response = httpx.post("https://payment-api.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()
```

## Next Steps

- Learn about [Components](components/index.md) - Deep dive into windows, trackers, trippers, retries, and permits
- See [Examples](examples.md) - Real-world usage patterns
- Read [API Reference](api/core.md) - Complete API documentation
