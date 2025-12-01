# Comparison with Other Libraries

This page compares Fluxgate with other Python circuit breaker libraries to help you choose the right tool for your needs.

## Overview

| Library | Python | License |
|---------|--------|---------|
| [![circuitbreaker](https://img.shields.io/github/stars/fabfuel/circuitbreaker?label=circuitbreaker&logo=github)](https://github.com/fabfuel/circuitbreaker) | ![Python](https://img.shields.io/pypi/pyversions/circuitbreaker) | ![License](https://img.shields.io/github/license/fabfuel/circuitbreaker) |
| [![pybreaker](https://img.shields.io/github/stars/danielfm/pybreaker?label=pybreaker&logo=github)](https://github.com/danielfm/pybreaker) | ![Python](https://img.shields.io/pypi/pyversions/pybreaker) | ![License](https://img.shields.io/github/license/danielfm/pybreaker) |
| [![aiobreaker](https://img.shields.io/github/stars/arlyon/aiobreaker?label=aiobreaker&logo=github)](https://github.com/arlyon/aiobreaker) | ![Python](https://img.shields.io/pypi/pyversions/aiobreaker) | ![License](https://img.shields.io/github/license/arlyon/aiobreaker) |
| [![pycircuitbreaker](https://img.shields.io/github/stars/etimberg/pycircuitbreaker?label=pycircuitbreaker&logo=github)](https://github.com/etimberg/pycircuitbreaker) | ![Python](https://img.shields.io/pypi/pyversions/pycircuitbreaker) | ![License](https://img.shields.io/github/license/etimberg/pycircuitbreaker) |

## Feature Comparison

| Feature | Fluxgate | circuitbreaker | pybreaker | aiobreaker |
|---------|:--------:|:--------------:|:---------:|:----------:|
| **Sync support** | Yes | Yes | Yes | No |
| **Async support** | Yes (asyncio) | Yes | Tornado only | Yes (asyncio) |
| **Trigger condition** | Failure rate | Consecutive failures | Consecutive failures | Consecutive failures |
| **Sliding window** | Yes (Count/Time) | No | No | No |
| **Composable conditions** | Yes (`&`, `\|`) | No | No | No |
| **Latency-based trigger** | Yes (AvgLatency, SlowRate) | No | No | No |
| **Fallback** | Yes | Yes | No | No |
| **Redis storage** | No | No | Yes | Yes |
| **Listeners/Monitoring** | Yes (Log, Prometheus, Slack) | Yes (Monitor) | Yes | Yes |
| **Type hints** | Complete | Partial | Partial | Partial |
| **HALF_OPEN control** | Yes (Permit) | 1 test call | success_threshold | 1 test call |

## Key Differences

### Trigger Conditions

Most circuit breaker libraries use **consecutive failure count**:

```python
# circuitbreaker / pybreaker
# Opens after 5 consecutive failures
@circuit(failure_threshold=5)
def call_api():
    ...
```

Fluxgate uses **failure rate within a sliding window**:

```python
# Fluxgate
# Opens when failure rate exceeds 50% in the last 100 calls
cb = CircuitBreaker(
    window=CountWindow(size=100),
    tripper=MinRequests(10) & FailureRate(0.5),
    ...
)
```

This approach is more robust because:

- A single success doesn't reset the failure count
- Handles intermittent failures better
- Provides more accurate health assessment

### Composable Conditions

Fluxgate allows combining multiple conditions with logical operators:

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate, SlowRate

# Different thresholds for different states
tripper = MinRequests(10) & (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)

# Multiple trigger conditions
tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
```

### Latency-Based Triggers

Fluxgate can open the circuit based on response time, not just errors:

```python
from fluxgate.trippers import AvgLatency, SlowRate

# Open when average latency exceeds 2 seconds
tripper = MinRequests(10) & AvgLatency(2.0)

# Open when more than 30% of calls are slow (>1s)
cb = CircuitBreaker(
    tripper=MinRequests(10) & SlowRate(0.3),
    slow_threshold=1.0,  # 1 second
    ...
)
```

### Gradual Recovery

Fluxgate provides fine-grained control over HALF_OPEN state recovery:

```python
from fluxgate.permits import RampUp

# Gradually increase traffic from 10% to 80% over 60 seconds
cb = CircuitBreaker(
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

## When to Choose Each Library

### Choose Fluxgate when

- You need failure rate-based triggers (not just consecutive failures)
- You want latency-based circuit breaking
- You need composable, complex trigger conditions
- You're building modern asyncio applications
- You value complete type hints and IDE support

### Choose circuitbreaker when

- You need a simple, well-tested solution
- Consecutive failure counting is sufficient
- You want minimal configuration

### Choose pybreaker when

- You need Redis storage for distributed state
- You're using Tornado for async
- You need the `success_threshold` feature

### Choose aiobreaker when

- You need Redis storage with asyncio
- pybreaker's feature set meets your needs

## See Also

- [Circuit Breaker](../circuit-breaker.md) - Core concepts and usage
- [Components](../components/index.md) - Detailed component documentation
