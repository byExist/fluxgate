# Windows

Windows are the memory of the circuit breaker. They store recent call outcomes (like successes, failures, and response times) and provide the metrics that `trippers` use to decide whether to open the circuit.

Fluxgate provides two types of windows:

| Window Type | Tracking Method | Best For... |
|-------------|----------------|-----------|
| **CountWindow** | Last N calls | Services with stable traffic, where you want to evaluate a fixed number of recent operations. |
| **TimeWindow** | Last N seconds | Services with variable or bursty traffic, where time-based evaluation is more meaningful. |

---

## CountWindow

`CountWindow` tracks a fixed number of the most recent calls. It's a great choice for services with stable and predictable traffic patterns.

### How It Works {#countwindow-how-it-works}

It maintains a fixed-size circular buffer in memory. When a new call is recorded, it overwrites the oldest one if the window is full. This guarantees that the window always contains exactly the last N calls, providing a consistent volume for evaluation.

### Basic Usage {#countwindow-basic}

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow

# This breaker will base its decisions on the last 100 calls.
cb = CircuitBreaker(
    name="stable_api",
    window=CountWindow(size=100),
    ...
)
```

---

## TimeWindow

`TimeWindow` tracks calls that have occurred over the last N seconds. It's ideal for services with irregular or bursty traffic where a time-based perspective is more important than a call count.

### How It Works {#timewindow-how-it-works}

It uses a series of time-based buckets (one for each second in the window). When a call is recorded, its outcome is aggregated into the bucket corresponding to the current timestamp. Old buckets that fall outside the time window expire automatically and are reused.

This approach ensures that a sudden burst of failures doesn't dominate the metrics for too long.

### Basic Usage {#timewindow-basic}

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import TimeWindow

# This breaker will base its decisions on calls made in the last 60 seconds.
cb = CircuitBreaker(
    name="variable_traffic_api",
    window=TimeWindow(size=60),
    ...
)
```

## Choosing a Window

### Comparison {#comparison}

| Feature | CountWindow | TimeWindow |
|---|---|---|
| **Memory Usage** | Proportional to the number of calls (`size`). | Proportional to the duration in seconds (`size`). |
| **Traffic Spikes** | A burst of calls can quickly flush out old data. | Retains data for the full duration, smoothing out bursts. |
| **Low Traffic** | Gathers a full set of metrics faster. | May take longer to collect enough data to be meaningful. |
| **Evaluation Basis** | A fixed number of calls. | A fixed duration of time. |
| **Granularity** | Per-call. | Per-second. |

### When should I use `CountWindow`? {#choose-countwindow}

`CountWindow` is an excellent choice when you have:

- **Stable and predictable traffic**: The rate of calls doesn't fluctuate dramatically.
- **A need for memory efficiency**: It often consumes less memory than `TimeWindow` for equivalent coverage.
- **A desire for fast evaluation**: It can fill up and provide meaningful metrics quickly.

**Common use cases**: Internal microservice-to-microservice communication, background processing, or batch jobs.

### When should I use `TimeWindow`? {#choose-timewindow}

`TimeWindow` is generally recommended and is a safer default choice, especially when you have:

- **Irregular or bursty traffic**: It handles sudden spikes in traffic gracefully.
- **A need for time-based policies**: Your SLOs are likely defined in terms of time (e.g., "99.9% uptime over any 5-minute window").
- **A focus on real-time responsiveness**: It ensures that decisions are always based on a recent time period, regardless of call volume.

**Common use cases**: Public-facing APIs, user-facing services, or calls to volatile external services.

---

## Metrics

Both window types provide the same rich set of metrics for `trippers`.

```python
from fluxgate.windows import CountWindow
from fluxgate.metric import Record

window = CountWindow(size=100)

# Record calls manually
window.record(Record(success=True, duration=0.5))
window.record(Record(success=False, duration=1.2))

# Get the aggregated metric object
metric = window.get_metric()
print(f"Total calls: {metric.total_count}")
print(f"Failed calls: {metric.failure_count}")
print(f"Average duration: {metric.avg_duration}")
```

**Available Metrics:**

- `total_count`: Total number of calls recorded in the window.
- `failure_count`: Number of calls tracked as failures.
- `total_duration`: Sum of the durations of all calls.
- `slow_count`: Number of calls that exceeded the `slow_threshold`.
- `avg_duration`: The average response time (`total_duration / total_count`).
- `failure_rate`: The ratio of failed calls (`failure_count / total_count`).
- `slow_rate`: The ratio of slow calls (`slow_count / total_count`).

---

## Automatic Reset {#auto-reset}

Windows automatically clear their metrics when the circuit breaker transitions between states (e.g., `OPEN` → `HALF_OPEN` or `HALF_OPEN` → `CLOSED`). This ensures that each recovery attempt and each new `CLOSED` period begins with a clean slate.

## Performance Considerations {#performance}

| Operation | CountWindow | TimeWindow |
|---|---|---|
| **Memory** | O(N), where N is `size` | O(N), where N is `size` |
| **`record()`** | O(1) | O(1) |
| **`get_metric()`** | O(1) | O(1) |

Both implementations are highly optimized and designed for negligible overhead.

## Next Steps {#next-steps}

- [Trackers](trackers.md): Define what counts as a failure.
- [Trippers](trippers.md): Use these metrics to build tripping logic.
