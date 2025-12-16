# Permits

Permit strategies are the gatekeepers of the `HALF_OPEN` state. After a `retry` strategy decides it's time to test for recovery, the `permit` strategy decides *how* to test. It controls how many "probe" calls are allowed to pass through to the recovering service, preventing it from being overwhelmed by a sudden flood of traffic.

| Permit Type | Behavior | Best For... |
|---|---|---|
| **All** | Always allows all calls. | Testing or when no rate limiting is needed. |
| **Random** | Allows a random, fixed percentage of calls. | A simple, probabilistic approach to limiting traffic. |
| **RampUp** | Gradually increases the percentage of allowed calls. | A sophisticated approach that gently re-introduces traffic. |

---

## All

This strategy unconditionally allows all calls to pass through.

### How It Works {#all-how-it-works}

`All` simply returns `True` for every call, allowing 100% of traffic in the `HALF_OPEN` state. This is primarily useful for testing scenarios or when you want to rely solely on the `tripper` to control state transitions.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import All

# Allow all calls to pass through in the HALF_OPEN state.
cb = CircuitBreaker(
    name="api",
    permit=All(),
    ...
)
```

---

## Random

This strategy allows calls to pass through with a simple, fixed probability.

### How It Works {#random-how-it-works}

For every call that arrives in the `HALF_OPEN` state, `Random` generates a random number and allows the call if it's within the configured `ratio`. This decision is stateless and independent for each call.

- `Random(ratio=0.1)` allows roughly 10% of calls.
- `Random(ratio=0.8)` allows roughly 80% of calls.

This is a good choice for simple traffic limiting, especially when you want to start testing recovery at a constant rate immediately.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import Random

# Allow approximately 50% of calls to pass through in the HALF_OPEN state.
cb = CircuitBreaker(
    name="api",
    permit=Random(ratio=0.5),
    ...
)
```

---

## RampUp

This strategy provides a smoother, more gentle recovery by gradually increasing the admission rate over time. It's the recommended choice for most use cases.

### How It Works {#rampup-how-it-works}

`RampUp` linearly increases the allowed traffic ratio from an `initial` value to a `final` value over a set `duration`. The calculation is based on the time elapsed since the breaker entered the `HALF_OPEN` state.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import RampUp

# Start by allowing 10% of traffic, then ramp up to 80% over 60 seconds.
cb = CircuitBreaker(
    name="api",
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

**Example Progression:** For `RampUp(initial=0.1, final=0.8, duration=60.0)`:

- **At 0s:** 10% of calls are allowed.
- **At 15s:** 27.5% of calls are allowed.
- **At 30s:** 45% of calls are allowed.
- **At 60s (and beyond):** The rate is capped at the `final` value of 80%.

This strategy is excellent for protecting load-sensitive services like databases or external APIs.

---

## Choosing the Right Permit Strategy

### Comparison {#comparison}

| Feature | All | Random | RampUp |
|---|---|---|---|
| **Complexity** | Trivial | Simple | Medium |
| **Admission Rate** | 100% | Constant | Increases over time |
| **Recovery Style** | No limiting | Immediate fixed rate | Gradual ramp-up |
| **Load Spike Risk** | Highest | Higher (with a high ratio) | Very low |
| **Recommended?** | For testing only | For simple cases | **Recommended** |

### When should I use `Random`? {#choose-random}

`Random` is best for simple use cases where you need to quickly start testing recovery at a constant rate and aren't worried about overwhelming the downstream service.

**Recommended Settings:**

```python
from fluxgate.permits import Random

# Conservative (prioritizes stability)
permit = Random(ratio=0.3)

# Balanced
permit = Random(ratio=0.5)

# Aggressive (prioritizes fast recovery)
permit = Random(ratio=0.8)
```

### When should I use `RampUp`? {#choose-rampup}

`RampUp` is the **recommended** strategy for most use cases. It provides the safest recovery path by slowly re-introducing traffic, giving the service time to warm up caches, re-establish connections, and scale up.

**Recommended Settings:**

```python
from fluxgate.permits import RampUp

# Conservative recovery
permit = RampUp(initial=0.1, final=0.5, duration=120.0)

# Balanced recovery
permit = RampUp(initial=0.2, final=0.8, duration=60.0)

# Aggressive recovery
permit = RampUp(initial=0.5, final=1.0, duration=30.0)
```

---

## Relationship with Retry {#relationship-with-retry}

The `retry` and `permit` strategies work together to define your complete recovery process.

- **Retry**: Decides **when** to attempt recovery (the cooling-off period).
- **Permit**: Decides **how** to attempt recovery (the traffic allowance).

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

# A robust setup using Backoff and RampUp.
cb = CircuitBreaker(
    name="api",
    retry=Backoff(initial=10.0, multiplier=2.0),
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

**The recovery flow works like this:**

1. The `tripper` condition is met, and the circuit transitions to the `OPEN` state.
2. The `retry` strategy starts its timer. With `Backoff(initial=10.0)`, it waits for 10 seconds.
3. After 10 seconds, the circuit transitions to `HALF_OPEN`.
4. Now, the `permit` strategy takes over. For the next 60 seconds, it will gradually increase the percentage of allowed calls from 10% up to 80%.
5. If a probe call fails during this time, the circuit immediately trips back to `OPEN`, and the `retry` counter is incremented (the next wait time will be 20 seconds).
6. If all probe calls succeed, the circuit transitions back to `CLOSED`, and normal operation resumes.

## Next Steps {#next-steps}

- [Listeners](listeners/index.md): Monitor these state changes and get notified.
- [Circuit Breaker Overview](../circuit-breaker.md): See how all the components fit together.
