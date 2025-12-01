# Circuit Breaker

Circuit Breaker is a design pattern that automatically blocks calls to failing services in distributed systems to prevent cascading failures.

## Core Concepts {#core-concepts}

Circuit Breaker works like an electrical circuit breaker:

- In normal state, all calls are allowed (circuit is closed)
- When failures exceed threshold, calls are blocked (circuit opens)
- After some time, recovery is tested (half-open state)

## State Transitions {#state-transitions}

Circuit Breaker has 6 states:

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

### CLOSED {#state-closed}

**Normal operating state**

- All calls pass through to the actual service
- Continuously monitors failure metrics
- Transitions to OPEN when Tripper condition is met

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import All
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=All(),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),  # Only evaluate in CLOSED state
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)
```

### OPEN {#state-open}

**Call blocking state**

- All calls immediately raise `CallNotPermittedError`
- Protects failing service and prevents resource waste
- Transitions to HALF_OPEN after duration based on Retry strategy

```python
from fluxgate.errors import CallNotPermittedError

@cb
def call_api():
    return requests.get("https://api.example.com")

try:
    result = call_api()
except CallNotPermittedError as e:
    print(f"Circuit is open: {e.message}")
    # Execute fallback logic
    return {"fallback": "data"}
```

### HALF_OPEN {#state-half-open}

**Recovery testing state**

- Allows limited calls based on Permit strategy
- Transitions to CLOSED on success, back to OPEN on failure
- Minimizes service load through gradual recovery

```python
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=All(),
    tripper=MinRequests(5) & FailureRate(0.3),  # Stricter criteria in HALF_OPEN
    retry=Cooldown(duration=60.0),
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),  # Start at 10%, gradual increase
)
```

### METRICS_ONLY {#state-metrics-only}

**Metrics collection only**

- All calls pass through to the actual service
- Collects metrics but never opens circuit
- Useful for monitoring tests before production deployment

```python
# Collect metrics before production deployment
cb.metrics_only()

# Later activate actual Circuit Breaker
cb.reset()
```

### DISABLED {#state-disabled}

**Circuit Breaker disabled**

- All calls pass through to the actual service
- No metrics collection
- Useful for debugging or emergencies

```python
# Disable Circuit Breaker in emergency
cb.disable()

# Re-enable later
cb.reset()
```

### FORCED_OPEN {#state-forced-open}

**Forcefully block calls**

- All calls immediately raise `CallNotPermittedError`
- No automatic recovery (requires manual reset)
- Useful for planned maintenance or emergency shutdown

```python
# Force circuit open for maintenance
cb.force_open()

# Recover after maintenance
cb.reset()
```

## Usage {#usage}

### Decorator Style {#decorator-usage}

The most common usage pattern.

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
    tracker=TypeOf(ConnectionError, TimeoutError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@cb
def charge_payment(amount: float):
    response = requests.post("https://payment.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()
```

### Direct Call Style {#call-usage}

Useful when you need to protect functions dynamically.

```python
def process_payment(amount: float):
    response = requests.post("https://payment.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()

# Call through Circuit Breaker
result = cb.call(process_payment, amount=100.0)
```

### Async Support {#async-usage}

Full support for asyncio applications.

!!! note
    AsyncCircuitBreaker limits the number of concurrent calls in HALF_OPEN state using the `max_half_open_calls` parameter. The default is 10, and concurrency is controlled using asyncio.Semaphore. This limit prevents overwhelming a service that is still recovering.

```python
import httpx
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.ConnectError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
    max_half_open_calls=5,  # Limit concurrent calls in HALF_OPEN (default: 10)
)

@cb
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()

# Usage
result = await fetch_data()
```

## Info {#info}

Check current state and metrics of Circuit Breaker.

```python
info = cb.info()
print(f"Circuit: {info.name}")
print(f"State: {info.state}")
print(f"Changed at: {info.changed_at}")
print(f"Reopens: {info.reopens}")
print(f"Metrics: {info.metrics}")

# Example output:
# Circuit: payment_api
# State: closed
# Changed at: 1234567890.123
# Reopens: 0
# Metrics: Metric(total_count=100, failure_count=5, total_duration=45.2, slow_count=3)
```

## Manual Control {#manual-control}

Manually control Circuit Breaker when needed.

```python
# Reset to CLOSED (also clears metrics)
cb.reset()

# Transition to METRICS_ONLY
cb.metrics_only()

# Transition to DISABLED
cb.disable()

# Transition to FORCED_OPEN
cb.force_open()

# Change state without notifying listeners
cb.reset(notify=False)
```

## Error Handling {#error-handling}

How to handle errors when circuit is open.

### Using fallback parameter (recommended) {#fallback-parameter}

Using the `fallback` parameter, a fallback function is automatically called on any exception.

```python
# Fallback function receives the exception as argument
def handle_error(e: Exception) -> dict:
    if isinstance(e, CallNotPermittedError):
        return get_cached_data()  # Circuit open
    if isinstance(e, TimeoutError):
        return get_stale_data()   # Timeout
    raise e  # Re-raise other exceptions

@cb(fallback=handle_error)
def api_call() -> dict:
    return requests.get("https://api.example.com").json()

# Usage: Fallback is automatically called on exception
result = api_call()
```

### Using call_with_fallback {#call-with-fallback}

You can also explicitly specify a fallback when calling.

```python
result = cb.call_with_fallback(
    fetch_from_api,
    lambda e: get_cached_data(),
)
```

### Manual try/except approach {#manual-try-except}

```python
from fluxgate.errors import CallNotPermittedError

@cb
def api_call():
    return requests.get("https://api.example.com")

try:
    result = api_call()
except CallNotPermittedError:
    # Circuit is open - Fallback handling
    result = get_cached_data()
except Exception as e:
    # Actual service error
    logging.error(f"API call failed: {e}")
    raise
```

## Complete Example {#complete-example}

Complete example ready for production use.

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate, SlowRate
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
        (Closed() & (FailureRate(0.6) | SlowRate(0.3))) |    # CLOSED: 60% failure or 30% slow calls
        (HalfOpened() & (FailureRate(0.5) | SlowRate(0.2)))  # HALF_OPEN: 50% failure or 20% slow calls
    ),
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0,
        jitter_ratio=0.1  # Prevent thundering herd
    ),
    permit=RampUp(
        initial=0.1,      # Start at 10%
        final=0.5,        # Increase to 50%
        duration=60.0     # Over 60 seconds
    ),
    listeners=[LogListener(), PrometheusListener()],
    slow_threshold=3.0,  # Mark calls over 3 seconds as slow
)

@payment_cb
def charge_payment(amount: float):
    response = httpx.post(
        "https://payment-api.example.com/charge",
        json={"amount": amount},
        timeout=5.0
    )
    response.raise_for_status()
    return response.json()

# Usage
try:
    result = charge_payment(amount=100.0)
    print(f"Payment successful: {result}")
except CallNotPermittedError:
    print("Payment service is temporarily unavailable")
    # Fallback: Queue payment
    queue_payment(amount=100.0)
except httpx.HTTPStatusError as e:
    print(f"Payment failed with status {e.response.status_code}")
    raise
```

## Next Steps {#next-steps}

- [Components](components/index.md) - Learn components that make up Circuit Breaker
- [Examples](examples.md) - Real-world usage patterns and scenarios
- [API Reference](api/core.md) - Complete API documentation
