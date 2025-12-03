# Design & Inspiration

This document explains the core design philosophy of Fluxgate, the projects that inspired it, and the rationale behind key architectural decisions.

## The Name

A [fluxgate magnetometer](https://en.wikipedia.org/wiki/Magnetometer#Fluxgate_magnetometer) is a sensor that detects changes in magnetic fields by monitoring saturation states and responding when a threshold is exceeded. This mirrors how a circuit breaker monitors a system's health and "trips" when a failure threshold is passed.

## Inspiration

Fluxgate's design is heavily influenced by two fantastic, industry-proven projects.

### Resilience4j

[Resilience4j](https://resilience4j.readme.io/) is a lightweight, popular fault tolerance library for Java. Fluxgate borrows its most critical concept: the use of **sliding windows** for tracking service health.

Unlike simpler patterns that only track consecutive failures, a sliding window (either count-based or time-based) provides a much more accurate and robust assessment of a service's health over a recent period.

```python
# Fluxgate's sliding window approach is directly inspired by Resilience4j.
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # Tracks the last 100 calls.
window = TimeWindow(size=60)    # Tracks calls in the last 60 seconds.
```

### Django REST Framework

[Django's permission system](https://www.django-rest-framework.org/api-guide/permissions/#how-permissions-are-determined) uses a brilliant and highly flexible pattern of **composable objects** combined with logical operators (`&`, `|`, `~`).

<!--pytest.mark.skip-->

```python
# In Django REST Framework, complex rules are built by combining simple permission classes.
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class MyView(APIView):
    permission_classes = [IsAuthenticated & IsAdminUser]
```

Fluxgate applies this exact same philosophy to its `Tracker` and `Tripper` components. Instead of forcing users to learn a complex configuration schema or use a clunky builder pattern, it provides simple, reusable building blocks that can be combined to create sophisticated rules.

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# Complex tripping logic is created by combining simple trippers.
tripper = MinRequests(10) & (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)
```

This composable approach is at the heart of Fluxgate's flexibility.

---

## Design Decisions

Fluxgate makes two intentional design choices that differ from some other libraries.

### No Distributed State Sharing

Fluxgate's circuit breakers manage their state entirely within the application's process. There is no built-in support for sharing state across multiple processes or servers (e.g., via Redis).

This was a deliberate decision based on the core purpose of the circuit breaker pattern. The goal is to protect an application from repeatedly calling an unhealthy service. This can be achieved effectively without distributed state.

- **Independent Assessment**: If a downstream service is unhealthy, every instance of your application will naturally detect this through its own failed calls. The circuits will open independently and correctly on each server.
- **Simplicity and Resilience**: Adding a dependency on a distributed state store (like Redis) introduces a new network dependency, a new point of failure, and significant operational complexity. A failure in the state store could disable the entire circuit breaking mechanism.
- **Performance**: Relying on in-process memory is significantly faster than making a network call to check the state of the circuit on every request.

By keeping state local, Fluxgate remains lightweight, fast, and resilient, with zero external dependencies.

### `CircuitBreaker` is Not Thread-Safe

For concurrent applications, Fluxgate strongly encourages using `AsyncCircuitBreaker` with `asyncio`, not multi-threading with `CircuitBreaker`.

The standard `CircuitBreaker` class is **not thread-safe**. This is an intentional choice reflecting the current state of Python's concurrency ecosystem.

- Due to Python's Global Interpreter Lock (GIL), multi-threading is not an effective strategy for parallelizing CPU-bound code and offers limited benefits for I/O-bound code compared to `asyncio`.
- The modern Python ecosystem has overwhelmingly embraced `asyncio` for high-performance I/O-bound tasks. Web frameworks (FastAPI, Starlette, aiohttp), database drivers (asyncpg), and HTTP clients (httpx) are all built on the `asyncio` event loop.
- `AsyncCircuitBreaker` is the natural, idiomatic, and most performant way to use a circuit breaker in these modern applications.

Focusing on a first-class `asyncio` experience provides a safer, more efficient, and more future-proof library.

## See Also

- [Comparison](comparison.md): See how Fluxgate compares to other Python libraries.
- [Components Overview](../components/index.md): Dive into the components that make up the library.
