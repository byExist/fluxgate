# Examples

This page provides practical, real-world examples to help you get started with Fluxgate.

---

## 1. Protecting an External API Call

This is the most common use case. The goal is to protect our application from a slow or failing external service.

With default settings, Fluxgate will:

- Track failures over the last 100 calls
- Trip at 50% failure rate (after 100 calls minimum)
- Wait 60 seconds before recovery
- Allow 50% of calls during recovery

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.trackers import TypeOf

cb = CircuitBreaker(
    name="payment_api",
    tracker=TypeOf(httpx.HTTPError),  # Only track HTTP errors
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

---

## 2. Integrating with a Web Framework (FastAPI)

When integrating with a web framework, you typically want to catch a `CallNotPermittedError` and return a user-friendly error response, like a `503 Service Unavailable`.

<!--pytest.mark.skip-->

```python
from fastapi import FastAPI, HTTPException
import httpx
from fluxgate import AsyncCircuitBreaker, CallNotPermittedError
from fluxgate.trackers import TypeOf
from fluxgate.retries import Cooldown

app = FastAPI()

# A single circuit breaker for a critical external service.
external_api_cb = AsyncCircuitBreaker(
    name="external_product_api",
    tracker=TypeOf(httpx.HTTPError),
    retry=Cooldown(duration=30.0),  # Shorter cooldown for faster recovery
)

# A separate function for your core logic is a good practice.
@external_api_cb
async def fetch_product_data(product_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/products/{product_id}")
        response.raise_for_status()
        return response.json()

@app.get("/products/{product_id}")
async def get_product(product_id: str):
    try:
        data = await fetch_product_data(product_id)
        return data
    except CallNotPermittedError:
        # The circuit is open, return a 503 error.
        raise HTTPException(
            status_code=503,
            detail="The external product service is currently unavailable. Please try again later."
        )
    except httpx.HTTPStatusError as e:
        # The external service returned an error.
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
```

---

## 3. Applying Different Policies per Service

It's common to have different circuit breakers for different external services, each with its own tailored policy. A high-criticality service like payments might have a more conservative configuration than a less critical one like inventory.

```python
import httpx
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import TimeWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import MinRequests, FailureRate, FailureStreak
from fluxgate.retries import Backoff

# More conservative policy for the critical payment service.
# FailureStreak provides fast protection during cold start before MinRequests is met.
payment_cb = AsyncCircuitBreaker(
    name="payment_service",
    window=TimeWindow(size=300),
    tracker=TypeOf(httpx.HTTPError),
    tripper=FailureStreak(5) | (MinRequests(20) & FailureRate(0.4)),
    retry=Backoff(initial=30.0, max_duration=600.0),
)

# More aggressive policy for the less critical inventory service.
inventory_cb = AsyncCircuitBreaker(
    name="inventory_service",
    window=TimeWindow(size=60),
    tracker=TypeOf(httpx.HTTPError),
    tripper=MinRequests(10) & FailureRate(0.6),
    retry=Backoff(initial=10.0, max_duration=300.0),
)

@payment_cb
async def charge_payment(amount: float):
    pass

@inventory_cb
async def check_inventory(product_id: str):
    pass
```

---

## 4. Handling Fallbacks

When a call is blocked or fails, you often want to execute alternative logic, such as returning cached data. This is known as a "fallback".

### Using the `fallback` Decorator Argument (Recommended)

This is the cleanest approach. The provided function is called automatically whenever the protected function raises **any** exception. Your fallback function receives the exception instance, so you can decide how to handle it.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker, CallNotPermittedError

# Placeholder for a function that gets data from a cache.
def get_cached_data(e: Exception):
    print(f"Returning cached data due to: {type(e).__name__}")
    return {"source": "cache"}

# The fallback is only called if fetch_from_api raises an exception.
@cb(fallback=get_cached_data)
def fetch_data_with_fallback() -> dict:
    # ... logic to fetch from the live API ...
    raise httpx.ConnectError("Connection failed!")

# Usage: The fallback is invoked automatically.
result = fetch_data_with_fallback() # Returns {"source": "cache"}
```

### Using `call_with_fallback`

This is useful when you can't use a decorator. It works just like the `fallback` argument.

<!--pytest.mark.skip-->

```python
def fetch_from_api():
    # ...
    pass

# The fallback is only called if fetch_from_api raises an exception.
result = cb.call_with_fallback(
    fetch_from_api,
    fallback_func=get_cached_data,
)
```

### Manual `try...except`

For maximum control, you can use a standard `try...except` block. This gives you the most flexibility but is also more verbose.

<!--pytest.mark.skip-->

```python
from fluxgate import CallNotPermittedError

@cb
def fetch_data():
    # ...
    pass

try:
    result = fetch_data()
except CallNotPermittedError as e:
    # This block executes ONLY when the circuit is open.
    print("Circuit is open, returning fallback.")
    result = get_cached_data(e)
except httpx.HTTPError as e:
    # This block executes on other specific errors.
    print(f"API call failed: {e}, returning fallback.")
    result = get_cached_data(e)
```

---

## 5. Advanced Configuration Patterns

### Custom Error Tracking

A `tracker` lets you define precisely what counts as a failure. For example, you can ignore 4xx client errors while tracking 5xx server errors.

<!--pytest.mark.skip-->

```python
import httpx
from fluxgate.trackers import Custom

# This function returns True only for errors we want to track.
def is_retriable_server_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        # 5xx errors are failures, but 4xx errors are not.
        return e.response.status_code >= 500
    # Also track network errors.
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

cb = CircuitBreaker(
    name="api_client",
    tracker=Custom(is_retriable_server_error),
    ...
)
```

### Different Thresholds per State

You can use `Closed()` and `HalfOpened()` trippers to create stricter rules for recovery attempts.

<!--pytest.mark.skip-->

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

cb = CircuitBreaker(
    name="api",
    # Use different tripping conditions for the CLOSED and HALF_OPEN states.
    tripper=(
        (Closed() & MinRequests(20) & FailureRate(0.6)) |
        (HalfOpened() & MinRequests(5) & FailureRate(0.5)) # Stricter
    ),
    ...
)
```

### Factory for Dynamic Creation

A factory function is a powerful pattern for creating and managing many similar circuit breakers without repeating code.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Cooldown
from fluxgate.windows import CountWindow
from fluxgate.trippers import MinRequests, FailureRate

def circuit_breaker_factory(name: str, policy: str) -> CircuitBreaker:
    """Creates a circuit breaker based on a predefined policy name."""
    if policy == "strict":
        return CircuitBreaker(
            name=name,
            tripper=MinRequests(20) & FailureRate(0.4),
        )
    elif policy == "lenient":
        return CircuitBreaker(
            name=name,
            window=CountWindow(50),
            tripper=MinRequests(10) & FailureRate(0.7),
            retry=Cooldown(30.0),
        )
    else:
        raise ValueError(f"Unknown policy: {policy}")

# Create breakers on the fly
checkout_cb = circuit_breaker_factory("checkout", "strict")
recommendation_cb = circuit_breaker_factory("recommendations", "lenient")
```

## Next Steps

- [Components Overview](components/index.md): Dive deeper into each component.
- [Listeners Overview](components/listeners/index.md): Learn how to monitor your circuit breakers.
- [API Reference](api/core.md): Explore the complete API documentation.
