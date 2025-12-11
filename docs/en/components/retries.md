# Retries

A Retry strategy defines the "cooling-off" period for a circuit breaker. It controls when the breaker should attempt to recover by transitioning from the `OPEN` state to the `HALF_OPEN` state. Choosing the right strategy is key to balancing fast recovery with giving a struggling service enough time to heal.

| Retry Type | Transition Timing | Best For... |
|---|---|---|
| **Always** | Immediately | Non-critical services where immediate retries are acceptable. |
| **Never** | Manual only | When recovery requires manual intervention by an operator. |
| **Cooldown** | After a fixed delay | A simple, predictable wait time before attempting recovery. |
| **Backoff** | After an exponentially increasing delay | An adaptive approach that waits longer after repeated failures. |

---

## Always

This strategy moves the circuit to `HALF_OPEN` immediately after it opens. On any subsequent call, it will attempt a recovery.

!!! warning "Use with Caution"
    `Always` can be dangerous, as it encourages a "thundering herd" problem where many clients retry simultaneously, overwhelming a service that is trying to recover. It's best used for non-critical services where failures are known to be very brief.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Always

# Not generally recommended.
cb = CircuitBreaker(name="api", retry=Always(), ...)
```

---

## Never

This strategy keeps the circuit in the `OPEN` state indefinitely until it is manually reset. This is useful when a service requires human intervention to be fixed.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Never

cb = CircuitBreaker(name="api", retry=Never(), ...)

# An operator must manually reset the breaker after fixing the service.
cb.reset()
```

---

## Cooldown

This is a simple and common strategy that waits for a fixed `duration` (in seconds) before moving to `HALF_OPEN`.

It's a good default choice for services that tend to recover in a predictable amount of time.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Cooldown

# Wait for 60 seconds before the first recovery attempt.
cb = CircuitBreaker(
    name="api",
    retry=Cooldown(duration=60.0),
    ...
)
```

---

## Backoff

This is the most robust and recommended strategy. It increases the wait time exponentially after each consecutive failure, giving a struggling service more and more time to recover.

The wait time is calculated as `initial * (multiplier ** consecutive_failures)`.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff

# The wait time starts at 10s, doubles after each failed recovery attempt,
# and is capped at a maximum of 300s.
cb = CircuitBreaker(
    name="api",
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0
    ),
    ...
)
# Sequence of wait times:
# 1st attempt -> 10s
# 2nd attempt -> 20s
# 3rd attempt -> 40s
# 4th attempt -> 80s
# 5th attempt -> 160s
# 6th+ attempt -> 300s (capped by max_duration)
```

---

## Choosing the Right Retry Strategy

### Comparison {#comparison}

| Feature | Always | Never | Cooldown | Backoff |
|---|---|---|---|---|
| **Recovery** | Immediate | Manual | Fixed Delay | Exponential Delay |
| **Service Load** | High | None | Medium | Low |
| **Handles Repeated Failures?** | No | N/A | No | Yes |
| **Complexity** | Very Simple | Very Simple | Simple | Medium |
| **Recommended?** | No | For special cases | Good default | **Recommended** |

### When should I use `Always`? {#choose-always}

Only for non-critical services where failures are known to be extremely brief and the service can handle a high volume of retries.

### When should I use `Never`? {#choose-never}

When a service requires manual intervention to fix. The circuit breaker will not attempt to recover on its own.

- **Use case**: During a planned deployment or when a service is taken down for maintenance.

### When should I use `Cooldown`? {#choose-cooldown}

This is a great, simple default. It's best when you have a general idea of how long the service takes to recover.

- **Use case**: Protecting a service that has a predictable recovery time, like an external API with a fixed rate-limiting window.

### When should I use `Backoff`? {#choose-backoff}

This is the **recommended** strategy for most use cases. It gracefully backs off from a struggling service, giving it more time to recover after repeated failures.

- **Use case**: Protecting a critical downstream service that may be slow to restart or recover from an outage.

### A Note on Jitter {#using-jitter}

!!! tip "Always Add Jitter"
    For both `Cooldown` and `Backoff`, it is highly recommended to add **jitter**. Jitter adds a small amount of randomness to the wait time, which helps prevent a "thundering herd" scenario where multiple instances of your service all try to recover at the exact same time.

```python
from fluxgate.retries import Cooldown, Backoff

# For a 60s cooldown, jitter adds a +/- 6s random variation (54s to 66s).
retry_cooldown = Cooldown(duration=60.0, jitter_ratio=0.1)

# The same applies to each step of the backoff.
retry_backoff = Backoff(initial=10.0, jitter_ratio=0.1)
```

## Next Steps {#next-steps}

- [Permits](permits.md): Configure how many "probe" calls are allowed during the `HALF_OPEN` recovery state.
- [Trippers](trippers.md): Define the conditions that cause the circuit to trip in the first place.
