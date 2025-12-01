# Trippers

Trippers evaluate metrics collected by Windows to determine circuit state transitions. Multiple conditions can be combined using logical operators (`&`, `|`).

| Tripper Type | Condition | Use Case |
|--------------|-----------|----------|
| **Closed** | When in CLOSED state | State-specific conditions |
| **HalfOpened** | When in HALF_OPEN state | State-specific conditions |
| **MinRequests** | Minimum call count met | Ensure sample size |
| **FailureRate** | Failure rate exceeds threshold | Error rate-based blocking |
| **AvgLatency** | Average latency exceeds threshold | Performance-based blocking |
| **SlowRate** | Slow call rate exceeds threshold | Slow response-based blocking |

## Closed

Returns true only when circuit is in CLOSED state.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import Closed, FailureRate

# Check failure rate only when CLOSED
cb = CircuitBreaker(
    name="api",
    tripper=Closed() & FailureRate(0.5),
    ...
)
```

## HalfOpened

Returns true only when circuit is in HALF_OPEN state.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import HalfOpened, FailureRate

# Apply stricter criteria when HALF_OPEN
cb = CircuitBreaker(
    name="api",
    tripper=HalfOpened() & FailureRate(0.3),
    ...
)
```

## MinRequests

Returns true only when minimum call count is met.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import MinRequests, FailureRate

# Check failure rate after minimum 10 calls
cb = CircuitBreaker(
    name="api",
    tripper=MinRequests(10) & FailureRate(0.5),
    ...
)
```

## FailureRate

Returns true when failure rate exceeds threshold.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import FailureRate

# Open circuit when failure rate exceeds 50%
cb = CircuitBreaker(
    name="api",
    tripper=FailureRate(0.5),
    ...
)
```

## AvgLatency

Returns true when average latency exceeds threshold.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import AvgLatency

# Open circuit when average response time exceeds 2 seconds
cb = CircuitBreaker(
    name="api",
    tripper=AvgLatency(2.0),
    ...
)
```

## SlowRate

Returns true when slow call rate exceeds threshold.

!!! warning
    To use `SlowRate`, you must set the `slow_threshold` parameter in CircuitBreaker. Calls that take longer than this value are considered "slow calls". The default is `inf` (infinity), so without setting it, all calls are considered "fast" and SlowRate will always be 0%.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import SlowRate

# Open circuit when slow calls exceed 30%
cb = CircuitBreaker(
    name="api",
    tripper=SlowRate(0.3),
    slow_threshold=1.0,  # Calls over 1 second are considered slow
    ...
)
```

## Logical Operators {#operators}

Trippers can be combined with logical operators.

### AND (`&`) - All Conditions

```python
from fluxgate.trippers import MinRequests, FailureRate

# Minimum 10 calls AND failure rate >= 50%
tripper = MinRequests(10) & FailureRate(0.5)
```

### OR (`|`) - Any Condition

```python
from fluxgate.trippers import FailureRate, SlowRate

# Failure rate >= 50% OR slow call rate >= 30%
tripper = FailureRate(0.5) | SlowRate(0.3)
```

### Complex Combinations

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# CLOSED: Min 10 calls + 50% failure rate
# HALF_OPEN: Min 5 calls + 30% failure rate
tripper = (
    (Closed() & MinRequests(10) & FailureRate(0.5)) |
    (HalfOpened() & MinRequests(5) & FailureRate(0.3))
)
```

## Choosing a Tripper {#choosing-a-tripper}

### Comparison {#comparison}

| Feature | Closed/HalfOpened | MinRequests | FailureRate | AvgLatency | SlowRate |
|---------|------------------|-------------|-------------|------------|--------------|
| **Purpose** | State-specific conditions | Ensure sample size | Check error rate | Check avg performance | Check slow call rate |
| **Standalone** | No | No | Yes | Yes | Yes |
| **Common Combination** | AND with other Trippers | AND with other Trippers | AND with MinRequests | AND with MinRequests | AND with MinRequests |

### Use MinRequests {#use-minrequests}

!!! tip "Recommendation"
    - Include in almost all Tripper combinations
    - Prevents false positives with small sample sizes
    - Typically 10-20% of Window size

**Example:**

```python
# Window size 100, MinRequests 10
tripper = MinRequests(10) & FailureRate(0.5)
```

### FailureRate vs AvgLatency vs SlowRate {#rate-vs-latency}

**Choose FailureRate:**

- When error occurrence matters most
- When there's a clear failure criterion

**Choose AvgLatency:**

- When overall response time performance matters
- When average delay is the concern

**Choose SlowRate:**

- When the proportion of slow calls matters
- When controlling rate above specific threshold (slow_threshold)

### Combining Multiple Conditions {#combining-conditions}

```python
from fluxgate.trippers import MinRequests, FailureRate, SlowRate

# Failure rate OR slow call rate
tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
```

## Next Steps {#next-steps}

- [Retries](retries.md) - Retry policies when circuit is open
- [Permits](permits.md) - Call permission policies in HALF_OPEN state
