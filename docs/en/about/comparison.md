# Comparison with Other Libraries

This page provides a fair comparison between Fluxgate and other popular Python circuit breaker libraries. The goal is to highlight the different design philosophies and features to help you choose the best tool for your specific needs.

## Feature Comparison

| Feature | Fluxgate | circuitbreaker | pybreaker | aiobreaker |
|---|:---:|:---:|:---:|:---:|
| **Async Support** | ✅ | ✅ | (Tornado only) | ✅ |
| **Primary Trigger Logic** | Failure Rate, Consecutive Failures | Consecutive Failures | Consecutive Failures | Consecutive Failures |
| **Sliding Window** | ✅ (Count or Time) | ❌ | ❌ | ❌ |
| **Latency-Based Triggers** | ✅ (`AvgLatency`, `SlowRate`) | ❌ | ❌ | ❌ |
| **Composable Rules (&, \|)**| ✅ | ❌ | ❌ | ❌ |
| **Gradual Recovery (`RampUp`)**| ✅ | ❌ | ❌ | ❌ |
| **State Listeners** | ✅ | ❌ | ✅ | ✅ |
| **Built-in Monitoring** | ✅ (Prometheus, Slack) | ❌ | ❌ | ❌ |
| **External State Storage** | ❌ | ❌ | ✅ (Redis) | ✅ (Redis) |

---

## Key Differences

### 1. More Robust Triggering Logic

Most libraries trip based on a simple **consecutive failure count**. This can be brittle; a single successful call can reset the counter to zero, even if the service is still unhealthy.

Fluxgate uses a **failure rate over a sliding window**, which provides a much more accurate and stable assessment of service health. Additionally, Fluxgate supports `FailureStreak` for consecutive failure detection, which is useful for fast protection during cold start or complete service outage. You can combine both approaches for maximum resilience.

- **Other Libraries:**

    <!--pytest.mark.skip-->

    ```python
    # Opens after 5 failures in a row.
    @circuit(failure_threshold=5)
    def call_api(): ...
    ```

- **Fluxgate:**

    ```python
    from fluxgate import CircuitBreaker
    from fluxgate.trippers import MinRequests, FailureRate

    # Opens if the failure rate exceeds 50%
    cb = CircuitBreaker(
        name="api",
        tripper=MinRequests(10) & FailureRate(0.5),
    )
    ```

### 2. Composable and Flexible Rules

Fluxgate allows you to build sophisticated, fine-grained rules by combining simple components with logical operators (`&`, `|`). Other libraries typically support only a single condition.

- **Other Libraries:** A single threshold.
- **Fluxgate:**

    ```python
    from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate, SlowRate

    # Use different rules for different states.
    tripper = (
        (Closed() & MinRequests(10) & FailureRate(0.5)) |
        (HalfOpened() & MinRequests(5) & FailureRate(0.3))
    )

    # Trip on high failure rate OR high slow-call rate.
    tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
    ```

### 3. Latency-Based Triggers

Fluxgate can trip based on response time, not just exceptions. This is critical for detecting service "brownouts" (where a service is slow but not failing).

- **Other Libraries:** Can only react to exceptions.
- **Fluxgate:**

    ```python
    from fluxgate import CircuitBreaker
    from fluxgate.trippers import MinRequests, AvgLatency, SlowRate

    # Trip when average latency is over 2 seconds.
    tripper = MinRequests(10) & AvgLatency(2.0)

    # Trip when more than 30% of calls are slower than 1 second.
    cb = CircuitBreaker(
        name="api",
        tripper=MinRequests(10) & SlowRate(0.3),
        slow_threshold=1.0,  # Defines what "slow" means
    )
    ```

### 4. Gradual Recovery

When a service is recovering, you want to re-introduce traffic gradually to avoid overwhelming it. Fluxgate provides `RampUp` for this purpose. Other libraries typically only allow a single test call at a time.

- **Other Libraries:** Allow one call, then close the circuit if it succeeds.
- **Fluxgate:**

    <!--pytest.mark.skip-->

    ```python
    from fluxgate.permits import RampUp

    # Gradually increase traffic from 10% to 80% over 60 seconds.
    cb = CircuitBreaker(
        permit=RampUp(initial=0.1, final=0.8, duration=60.0),
        ...
    )
    ```

---

## When to Choose Each Library

### When should you choose `Fluxgate`?

You need the most robust and feature-rich circuit breaker.

- You want to trigger based on **failure rates**, **latency**, or **consecutive failures** (`FailureStreak`).
- You need **complex, composable rules** (e.g., different thresholds for different states).
- You want to **gradually ramp up** traffic during recovery.
- You are building a modern **asyncio** application.
- You value a fully **type-hinted** API for better developer experience.

### When should you choose `circuitbreaker`?

You need a simple, reliable, and widely-used library for basic use cases.

- Triggering on **consecutive failures** is sufficient for your needs.
- You value simplicity and minimal configuration.

### When should you choose `pybreaker` or `aiobreaker`?

You have a hard requirement for **sharing circuit breaker state** across multiple processes or servers.

- Your architecture requires a distributed state store (Redis).
- `pybreaker` is suitable for threaded or Tornado-based applications.
- `aiobreaker` is the `asyncio` equivalent of `pybreaker`.

## See Also

- [Design & Inspiration](design.md): Learn about the philosophy behind Fluxgate.
- [Components Overview](../components/index.md): Dive into the components that enable these features.
