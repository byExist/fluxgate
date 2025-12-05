# Trippers

Trippers are the brain of the circuit breaker. They analyze the metrics provided by a `window` to decide if the circuit should change state (e.g., from `CLOSED` to `OPEN`). By combining simple tripper components with logical operators (`&`, `|`), you can define sophisticated and precise rules for when your breaker should trip.

| Tripper Type | Condition | Use Case |
|---|---|---|
| **Closed** / **HalfOpened** | Checks if the circuit is in a specific state. | Create rules that only apply in a certain state. |
| **MinRequests** | Checks if the number of calls exceeds a minimum. | Prevent tripping on a small, statistically insignificant sample size. |
| **FailureRate** | Checks if the failure percentage is too high. | Trip when the error rate becomes unacceptable. |
| **AvgLatency** | Checks if the average response time is too slow. | Trip when overall performance degrades. |
| **SlowRate** | Checks if the percentage of slow calls is too high. | Trip based on the rate of outlier slow requests. |
| **FailureStreak** | Checks for consecutive failures. | Fast trip on cold start or complete service outage. |

---

## State-Based Trippers

These trippers check the current state of the circuit breaker, allowing you to create rules that apply only in `CLOSED` or `HALF_OPEN` states.

- `Closed()`: Returns `True` only when the circuit is in the `CLOSED` state.
- `HalfOpened()`: Returns `True` only when the circuit is in the `HALF_OPEN` state.

They are almost always used with the `&` operator to scope other conditions.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import Closed, HalfOpened, FailureRate

# Use different failure rate thresholds for CLOSED and HALF_OPEN states.
tripper = (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)
```

---

## Metric-Based Trippers

These trippers evaluate the metrics gathered by the `window`.

### MinRequests

`MinRequests(count)` returns `True` only after the window has recorded at least `count` calls. This is crucial for preventing the breaker from tripping on a small, statistically insignificant number of failures (e.g., 1 failure out of 2 calls is a 50% failure rate, but it's not enough data to act on).

```python
from fluxgate.trippers import MinRequests, FailureRate

# The breaker won't trip until at least 10 calls have been recorded.
tripper = MinRequests(10) & FailureRate(0.5)
```

### FailureRate

`FailureRate(rate)` returns `True` if the ratio of failed calls to total calls exceeds the `rate` (e.g., `0.5` for 50%).

```python
from fluxgate.trippers import FailureRate

# Trip if more than 50% of calls are failing.
tripper = FailureRate(0.5)
```

### AvgLatency

`AvgLatency(seconds)` returns `True` if the average response time of all calls in the window exceeds `seconds`.

```python
from fluxgate.trippers import AvgLatency

# Trip if the average response time is greater than 2 seconds.
tripper = AvgLatency(2.0)
```

### SlowRate

`SlowRate(rate)` returns `True` if the ratio of "slow" calls exceeds the `rate`. A call is considered "slow" if its duration exceeds the `slow_threshold` parameter (in seconds) on the `CircuitBreaker`.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import SlowRate

# Trip if more than 30% of calls are "slow".
cb = CircuitBreaker(
    name="api",
    tripper=SlowRate(0.3),
    slow_threshold=1.0,  # A call is slow if it takes longer than 1 second.
    ...
)
```

### FailureStreak

`FailureStreak(count)` returns `True` when the number of consecutive failures reaches `count`. This is useful for fast failure detection during cold start or when an external service is completely down.

```python
from fluxgate.trippers import FailureStreak, MinRequests, FailureRate

# Trip after 5 consecutive failures
tripper = FailureStreak(5)

# Combine with FailureRate for comprehensive protection:
# - Fast trip on 5 consecutive failures (cold start protection)
# - OR statistical trip after 20 requests with 50% failure rate
tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))
```

---

## Combining Trippers with Logical Operators {#operators}

You can create powerful and precise rules by combining trippers with logical operators.

### AND (`&`)

The `&` operator requires **all** conditions to be true. It's the most common way to combine trippers.

```python
from fluxgate.trippers import MinRequests, FailureRate

# Trip only if the window has at least 10 requests AND the failure rate is over 50%.
tripper = MinRequests(10) & FailureRate(0.5)
```

### OR (`|`)

The `|` operator requires **any** condition to be true.

```python
from fluxgate.trippers import FailureRate, SlowRate

# Trip if the failure rate is over 50% OR the slow call rate is over 30%.
tripper = FailureRate(0.5) | SlowRate(0.3)
```

### Complex Example

Here's how to create different rules for the `CLOSED` and `HALF_OPEN` states.

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# This rule translates to:
# - IF the state is CLOSED, trip if there are at least 10 requests and the failure rate is > 50%.
# - OR IF the state is HALF_OPEN, trip if there are at least 5 requests and the failure rate is > 30%.
tripper = (
    (Closed() & MinRequests(10) & FailureRate(0.5)) |
    (HalfOpened() & MinRequests(5) & FailureRate(0.3))
)
```

---

## Choosing the Right Tripper

### Comparison {#comparison}

| Feature | `Closed`/`HalfOpened` | `MinRequests` | `FailureRate` | `AvgLatency` | `SlowRate` | `FailureStreak` |
|---|---|---|---|---|---|---|
| **Purpose** | Apply rules to a specific state. | Ensure a meaningful sample size. | Check the ratio of failed calls. | Check the average performance. | Check the ratio of slow calls. | Fast trip on consecutive failures. |
| **Standalone?** | No | Almost never | Yes | Yes | Yes | Yes |
| **Commonly Combined With** | `&` with metric-based trippers | `&` with other metric-based trippers | `&` with `MinRequests` | `&` with `MinRequests` | `&` with `MinRequests` | `\|` with `MinRequests & FailureRate` |

### Always Use `MinRequests` {#use-minrequests}

!!! tip "Strong Recommendation"
    You should include `MinRequests` in almost every tripper combination. It prevents the circuit from making hasty decisions based on a small, statistically insignificant sample of calls. A good starting point is a value that is 10-20% of your window's size.

```python
from fluxgate.trippers import MinRequests, FailureRate

# For a CountWindow(size=100), a MinRequests of 10-20 is a sensible choice.
tripper = MinRequests(10) & FailureRate(0.5)
```

### `FailureRate` vs. `AvgLatency` vs. `SlowRate` {#rate-vs-latency}

- **Choose `FailureRate`** when you care most about explicit errors (exceptions). This is the most common and intuitive choice.

- **Choose `AvgLatency`** when you want to protect against a general slowdown or "brownout" where the service is responding, but too slowly. Be careful: a few very slow calls can skew the average.

- **Choose `SlowRate`** when you want to protect against outliers. It's often more robust than `AvgLatency` because it's less sensitive to a single, extremely slow call. It measures the *percentage* of calls that are slow, not the average slowness.

### Putting It All Together {#combining-conditions}

A robust configuration often combines multiple conditions.

```python
from fluxgate.trippers import MinRequests, FailureRate, SlowRate

# Trip if, after at least 10 calls, the failure rate exceeds 50% OR the slow rate exceeds 30%.
tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
```

## Next Steps {#next-steps}

- [Retries](retries.md): Define the policy for recovering from an `OPEN` state.
- [Permits](permits.md): Configure how to test for recovery in the `HALF_OPEN` state.
