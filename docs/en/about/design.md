# Design & Inspiration

This document explains Fluxgate's design decisions and the projects that influenced them.

## The Name

A [fluxgate magnetometer](https://en.wikipedia.org/wiki/Magnetometer#Fluxgate_magnetometer) is a sensor that detects changes in magnetic fields by monitoring saturation states and responding at thresholds. This mirrors how a circuit breaker monitors system health and trips when thresholds are exceeded.

## Inspiration

### Resilience4j

[Resilience4j](https://resilience4j.readme.io/) is a lightweight fault tolerance library for Java, inspired by Netflix Hystrix. Fluxgate borrows several key concepts from Resilience4j:

Resilience4j tracks call outcomes using sliding windows (count-based or time-based) rather than simple consecutive failure counting. This provides more accurate health assessment of services. Fluxgate adopts this approach.

```python
# Fluxgate's sliding window approach inspired by Resilience4j
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # Last 100 calls
window = TimeWindow(size=60)    # Last 60 seconds
```

### Django Permissions

[Django's permission system](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions) supports combining permissions using bitwise operators (`&`, `|`, `~`). This elegant pattern inspired Fluxgate's composable components.

```python
# Django REST framework's composable permissions
from rest_framework.views import APIView

class MyView(APIView):
    permission_classes = [IsAuthenticated & (IsAdminUser | IsStaff)]
```

Fluxgate applies the same pattern to Trippers and Trackers:

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# Composable trippers with logical operators
tripper = MinRequests(10) & (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)
```

```python
from fluxgate.trackers import TypeOf

# Composable trackers
tracker = TypeOf(ConnectionError, TimeoutError) & ~TypeOf(CancellationError)
```

This approach provides flexibility without complex configuration objects or builder patterns.

## Design Decisions

### No Distributed State Sharing

Fluxgate does not support distributed state sharing (e.g., Redis storage). Each CircuitBreaker instance manages state within a single process.

Distributed state is not a fundamental requirement of the circuit breaker pattern. The pattern's core purpose is to prevent cascading failures by quickly stopping calls to unhealthy services.

- Each process can independently assess the health of downstream services. If a service is unhealthy, all processes will naturally detect this through their own failures.
- Adding distributed state introduces network latency, additional failure points, and operational complexity. These costs often outweigh the benefits.

### Not Thread-Safe

`CircuitBreaker` is not thread-safe. For concurrent workloads, use `AsyncCircuitBreaker` with asyncio.

Currently, Python's Global Interpreter Lock (GIL) means that multi-threaded Python code doesn't achieve true parallelism for CPU-bound tasks. As a result, most I/O-bound Python applications benefit more from asyncio than from threading. Modern Python web frameworks (FastAPI, Starlette, aiohttp) are asyncio-based, making `AsyncCircuitBreaker` the natural choice.

## See Also

- [Comparison](comparison.md) - Compare with other Python libraries
- [Components](../components/index.md) - Detailed component documentation
