# Retries

Retry determines when to transition from OPEN to HALF_OPEN state.

| Retry Type | Transition Timing | Use Case |
|-----------|----------|----------|
| **Always** | Immediately | Quick recovery attempts |
| **Never** | No transition | Manual recovery |
| **Cooldown** | After fixed wait time | Fixed wait period |
| **Backoff** | Exponential backoff | Increasing wait on repeated failures |

## Always

Immediately attempts HALF_OPEN transition on every call.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Always

# Immediate recovery attempts
cb = CircuitBreaker(
    name="api",
    retry=Always(),
    ...
)
```

## Never

Keeps OPEN state until manual reset() is called.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Never

# Manual recovery only
cb = CircuitBreaker(
    name="api",
    retry=Never(),
    ...
)

# Manual recovery
cb.reset()
```

## Cooldown

Transitions to HALF_OPEN after a fixed wait period.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Cooldown

# Wait 60 seconds before recovery attempt
cb = CircuitBreaker(
    name="api",
    retry=Cooldown(duration=60.0),
    ...
)

# Add jitter to prevent thundering herd
cb = CircuitBreaker(
    name="api",
    retry=Cooldown(duration=60.0, jitter_ratio=0.1),  # ±10% random
    ...
)
```

## Backoff

Wait time increases exponentially with each retry.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff

# Start at 10s, double each time, max 300s
cb = CircuitBreaker(
    name="api",
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0
    ),
    ...
)
# Wait times by retry count:
# 0 → 10s
# 1 → 20s
# 2 → 40s
# 3 → 80s
# 4 → 160s
# 5+ → 300s

# Add jitter
cb = CircuitBreaker(
    name="api",
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0,
        jitter_ratio=0.1  # ±10% random
    ),
    ...
)
```

## Choosing a Retry {#choosing-a-retry}

### Comparison {#comparison}

| Feature | Always | Never | Cooldown | Backoff |
|---------|--------|-------|----------|---------|
| **Recovery Speed** | Immediate | Not possible | Fixed time | Gradual increase |
| **Service Load** | High | None | Medium | Low |
| **Repeated Failure Handling** | None | N/A | None | Excellent |
| **Complexity** | Simple | Simple | Simple | Medium |

### Choose Always {#choose-always}

**Best for:**

- Mostly transient failures
- Quick recovery is critical
- Service load is not a concern

**Examples:** Momentary network disconnection, temporary DNS errors

### Choose Never {#choose-never}

**Best for:**

- Manual intervention required
- Decision needed after monitoring

**Examples:** During deployment, service under maintenance

### Choose Cooldown {#choose-cooldown}

**Best for:**

- Predictable recovery time
- Fixed wait time is sufficient
- Thundering herd prevention needed (use jitter)

**Examples:** External API rate limits, scheduled maintenance

### Choose Backoff {#choose-backoff}

**Best for:**

- High likelihood of repeated failures
- Need to gradually reduce service load
- Recovery time is unpredictable

**Examples:** Service recovering from failure, overload conditions

### Using Jitter {#using-jitter}

**Add jitter when:**

- Multiple circuit breakers attempt recovery simultaneously
- Want to prevent thundering herd problem

```python
# jitter_ratio=0.1 → ±10% random
# duration=60.0 → actual wait: 54~66s
retry = Cooldown(duration=60.0, jitter_ratio=0.1)
```

## Next Steps {#next-steps}

- [Permits](permits.md) - Call permission policies in HALF_OPEN state
- [Trippers](trippers.md) - Circuit state transition conditions
