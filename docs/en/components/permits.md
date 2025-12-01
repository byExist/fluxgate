# Permits

Controls call admission in HALF_OPEN state. Helps stable recovery by gradually allowing traffic when the circuit attempts to recover.

| Permit Type | Behavior | Use Case |
|-------------|----------|----------|
| **Random** | Random admission with fixed probability | Simple traffic limiting |
| **RampUp** | Gradual increase over time | Smooth traffic recovery |

## Random

Randomly allows calls with a fixed probability.

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import Random

# Allow 50% of calls in HALF_OPEN state
cb = CircuitBreaker(
    name="api",
    permit=Random(ratio=0.5),
    ...
)
```

### How It Works {#random-how-it-works}

- Independent probability calculation for each call
- `ratio` value determines admission probability (0.0 to 1.0)
- Maintains constant rate regardless of time

### Use Cases {#random-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import Random

# Conservative recovery: Allow only 10%
cb = CircuitBreaker(
    name="conservative_api",
    permit=Random(ratio=0.1),
    ...
)

# Aggressive recovery: Allow 80%
cb = CircuitBreaker(
    name="aggressive_api",
    permit=Random(ratio=0.8),
    ...
)
```

## RampUp

Gradually increases admission rate over time.

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import RampUp

# Start at 10%, increase to 80% over 60 seconds
cb = CircuitBreaker(
    name="api",
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

### How It Works {#rampup-how-it-works}

- Measures elapsed time since HALF_OPEN transition
- Linearly increases admission rate: `initial + (final - initial) × (elapsed / duration)`
- Maintains `final` ratio after `duration` elapses

**Example: initial=0.1, final=0.8, duration=60 seconds**

- 0s: 10% allowed
- 15s: 27.5% allowed
- 30s: 45% allowed
- 45s: 62.5% allowed
- 60s+: 80% allowed

### Use Cases {#rampup-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import RampUp

# External API requiring gradual recovery
cb = CircuitBreaker(
    name="external_api",
    permit=RampUp(initial=0.1, final=0.9, duration=120.0),
    ...
)

# Internal service with fast recovery
cb = CircuitBreaker(
    name="internal_service",
    permit=RampUp(initial=0.3, final=1.0, duration=30.0),
    ...
)
```

## Choosing a Permit {#choosing-a-permit}

### Comparison {#comparison}

| Feature | Random | RampUp |
|---------|--------|--------|
| **Complexity** | Simple | Medium |
| **Admission Rate** | Constant | Increases over time |
| **Recovery Speed** | Immediate fixed rate | Gradual increase |
| **Load Spike** | Possible (with high ratio) | Minimized |
| **Use Case** | Simple traffic limiting | Stable gradual recovery |

### Choose Random {#choose-random}

**Best for:**

- Simple traffic control needed
- Immediate recovery at constant rate
- Load spikes not a concern

**Examples:** Internal services, time-critical recovery

**Recommended Settings:**

```python
# Conservative (stability first)
permit = Random(ratio=0.3)

# Balanced
permit = Random(ratio=0.5)

# Aggressive (fast recovery first)
permit = Random(ratio=0.8)
```

### Choose RampUp {#choose-rampup}

**Best for:**

- Gradual traffic increase needed
- Load spike prevention important
- External service protection needed

**Examples:** External APIs, databases, load-sensitive services

**Recommended Settings:**

```python
# Conservative recovery
permit = RampUp(initial=0.1, final=0.5, duration=120.0)

# Balanced recovery
permit = RampUp(initial=0.2, final=0.8, duration=60.0)

# Aggressive recovery
permit = RampUp(initial=0.5, final=1.0, duration=30.0)
```

## Relationship with Retry {#relationship-with-retry}

Permit and Retry work together to determine recovery strategy:

- **Retry**: Determines when to transition from OPEN → HALF_OPEN
- **Permit**: Determines call admission rate in HALF_OPEN state

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

# Gradual retry, slow ramp-up
cb = CircuitBreaker(
    name="api",
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0),
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

**Flow:**

1. Circuit transitions to OPEN state
2. `Retry` determines wait time (e.g., 10 seconds)
3. After 10 seconds, transitions to HALF_OPEN
4. `Permit` determines call admission (e.g., start 10%, gradual increase)
5. On success → CLOSED, on failure → OPEN again

## Next Steps {#next-steps}

- [Listeners](listeners/index.md) - Monitor circuit state changes
- [CircuitBreaker](../circuit-breaker.md) - Integrate all settings
