# Fluxgate

A composable circuit breaker library for Python.

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/fluxgate.svg)](https://pypi.org/project/fluxgate/)

## Installation

```bash
pip install fluxgate
```

## Quick Start

```python
from fluxgate import CircuitBreaker

cb = CircuitBreaker(name="my_api")

@cb
def call_api():
    return requests.get("https://api.example.com")
```

That's it. The circuit breaker will:

- Track the last 100 calls
- Open when failure rate exceeds 50% (after 100+ requests)
- Wait 60 seconds before testing recovery
- Gradually allow more calls as the service recovers

## Async Support

For async applications, use `AsyncCircuitBreaker`:

```python
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(name="my_api")

@cb
async def call_api():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com")
```

## Customization

Every component is customizable. You can apply different policies to different services based on their criticality:

```python
import httpx
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import TimeWindow
from fluxgate.trackers import TypeOf, Custom
from fluxgate.trippers import MinRequests, FailureRate, FailureStreak
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

# Track only 5xx errors and network failures (not 4xx client errors)
def is_server_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

# Conservative policy for critical payment service
payment_cb = AsyncCircuitBreaker(
    name="payment_service",
    window=TimeWindow(size=300),              # Track calls over 5 minutes
    tracker=Custom(is_server_error),          # Custom error filtering
    tripper=(
        FailureStreak(5) |                    # Trip on 5 consecutive failures OR
        (MinRequests(20) & FailureRate(0.4))  # 40% failure rate after 20 calls
    ),
    retry=Backoff(initial=30.0, max_duration=600.0),  # 30s, 60s, 120s... up to 10min
    permit=RampUp(0.1, 1.0, 60.0),            # Gradually allow 10% → 100% over 60s
)

# Aggressive policy for less critical inventory service
inventory_cb = AsyncCircuitBreaker(
    name="inventory_service",
    window=TimeWindow(size=60),               # Track calls over 1 minute
    tracker=TypeOf(httpx.HTTPError),          # Track all HTTP errors
    tripper=MinRequests(10) & FailureRate(0.6),  # 60% failure rate after 10 calls
    retry=Backoff(initial=10.0, max_duration=300.0),
)

@payment_cb
async def charge_payment(amount: float):
    async with httpx.AsyncClient() as client:
        response = await client.post("https://payment.example.com/charge", json={"amount": amount})
        response.raise_for_status()
        return response.json()

@inventory_cb
async def check_inventory(product_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://inventory.example.com/products/{product_id}")
        response.raise_for_status()
        return response.json()
```

### Components

| Component | Purpose | Examples |
|-----------|---------|----------|
| **Window** | How to track call history | `CountWindow(100)`, `TimeWindow(60)` |
| **Tracker** | Which exceptions to track | `All()`, `TypeOf(HTTPError)`, `Custom(func)` |
| **Tripper** | When to open the circuit | `MinRequests(n)`, `FailureRate(0.5)`, `FailureStreak(5)`, `SlowRate(0.5)`, `AvgLatency(1.0)`, `Closed()`, `HalfOpened()` |
| **Retry** | When to attempt recovery | `Cooldown(60.0)`, `Backoff(initial=10.0)`, `Always()`, `Never()` |
| **Permit** | How to allow calls during recovery | `All()`, `Random(0.5)`, `RampUp(0.1, 1.0, 60.0)` |

## Monitoring

Attach listeners to get notified on state transitions:

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener
from fluxgate.listeners.slack import SlackListener

cb = CircuitBreaker(
    name="my_api",
    listeners=[
        LogListener(),
        PrometheusListener(),
        SlackListener(channel="C123", token="xoxb-..."),
    ],
)
```

## Documentation

[Full documentation](https://byExist.github.io/fluxgate/)
