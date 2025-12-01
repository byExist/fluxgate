# Examples

Get started quickly with real-world use cases.

## Basic Usage

### HTTP API Protection

Protect external API calls with a circuit breaker.

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="payment_api",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@cb
def charge_payment(amount: float):
    response = httpx.post(
        "https://api.example.com/charge",
        json={"amount": amount}
    )
    response.raise_for_status()
    return response.json()
```

## Async Usage

### FastAPI Integration

Apply circuit breakers to FastAPI endpoints.

```python
from fastapi import FastAPI, HTTPException
import httpx
from fluxgate import AsyncCircuitBreaker, CallNotPermittedError
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

app = FastAPI()

cb = AsyncCircuitBreaker(
    name="external_api",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@app.get("/data")
async def get_data():
    try:
        @cb
        async def fetch():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                response.raise_for_status()
                return response.json()

        return await fetch()
    except CallNotPermittedError:
        raise HTTPException(status_code=503, detail="Service unavailable")
```

### Multiple Circuit Breakers

Create independent circuit breakers for each service.

```python
import httpx
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

# Per-service circuit breakers
payment_cb = AsyncCircuitBreaker(
    name="payment_service",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

inventory_cb = AsyncCircuitBreaker(
    name="inventory_service",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.3),
    retry=Cooldown(duration=30.0),
    permit=Random(ratio=0.7),
)

@payment_cb
async def charge_payment(amount: float):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://payment.example.com/charge",
            json={"amount": amount}
        )
        response.raise_for_status()
        return response.json()

@inventory_cb
async def check_inventory(product_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://inventory.example.com/products/{product_id}"
        )
        response.raise_for_status()
        return response.json()
```

## Advanced Usage

### Custom Error Tracking

Track only specific types of errors in the circuit breaker.

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

# Track only 5xx errors and network failures
def is_server_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

cb = CircuitBreaker(
    name="api_client",
    window=CountWindow(size=100),
    tracker=Custom(is_server_error),
    tripper=Closed() & MinRequests(20) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)
```

### Different Thresholds Per State

Apply different thresholds for CLOSED and HALF_OPEN states.

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    # CLOSED: 60% failure rate, HALF_OPEN: 50% failure rate
    tripper=MinRequests(20) & (
        (Closed() & FailureRate(0.6)) |
        (HalfOpened() & FailureRate(0.5))
    ),
    retry=Cooldown(duration=60.0),
    # Gradual traffic increase: 10% � 80% over 60s
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
)
```

### Fallback Handling

Perform alternative actions when exceptions occur. Using the `fallback` parameter, a fallback function is automatically called on any exception.

#### Using fallback with decorator

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

# Fallback function receives the exception as argument
def fallback_handler(e: Exception) -> dict:
    if isinstance(e, ConnectionError):
        return get_cached_data()
    raise e  # Re-raise other exceptions

@cb(fallback=fallback_handler)
def fetch_data() -> dict:
    return fetch_from_api()

# Usage: Fallback is automatically called on circuit open or error
result = fetch_data()
```

#### Using call_with_fallback

You can also explicitly specify a fallback when calling.

```python
# Pass function and fallback together
result = cb.call_with_fallback(
    fetch_from_api,
    lambda e: get_cached_data(),
)

# With arguments
result = cb.call_with_fallback(
    fetch_user_data,
    lambda e: {"user_id": user_id, "cached": True},
    user_id,  # Arguments passed to the original function
)
```

#### Async fallback

AsyncCircuitBreaker works the same way.

```python
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    # ... configuration
)

@cb(fallback=lambda e: {"status": "fallback"})
async def fetch_data() -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# Or use call_with_fallback
result = await cb.call_with_fallback(
    fetch_from_api,
    lambda e: get_cached_data(),
)
```

#### Manual try/except (legacy approach)

You can also handle exceptions directly without fallback.

```python
from fluxgate import CallNotPermittedError

@cb
def fetch():
    return fetch_from_api()

try:
    result = fetch()
except CallNotPermittedError:
    # When circuit is open
    result = get_cached_data()
except ConnectionError:
    # On connection failure
    result = get_cached_data()
```

### Factory Function

Create circuit breakers with different policies per endpoint.

```python
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate, SlowRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random
import httpx

def create_payment_circuit_breaker(
    endpoint: str,
    slow_threshold: float,
    failure_rate: float = 0.5,
    slow_rate: float = 0.5,
) -> AsyncCircuitBreaker:
    return AsyncCircuitBreaker(
        name=f"payment_{endpoint}",
        window=CountWindow(size=100),
        tracker=TypeOf(httpx.HTTPError),
        tripper=Closed() & MinRequests(10) & (
            FailureRate(failure_rate) | SlowRate(slow_rate, slow_threshold)
        ),
        retry=Cooldown(duration=60.0),
        permit=Random(ratio=0.5),
    )

# Store in variables
charge_cb = create_payment_circuit_breaker("charge", slow_threshold=2.0, failure_rate=0.3)
refund_cb = create_payment_circuit_breaker("refund", slow_threshold=3.0, failure_rate=0.3)
history_cb = create_payment_circuit_breaker("history", slow_threshold=0.5)

# Or use directly as decorator
@create_payment_circuit_breaker("charge", slow_threshold=2.0, failure_rate=0.3)
async def charge_payment(amount: float):
    ...
```

## Next Steps

- [Components](components/index.md) - Detailed component documentation
- [Listeners](components/listeners/index.md) - Monitoring and alerting setup
- [API Reference](api/core.md) - Complete API documentation
