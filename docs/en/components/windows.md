# Windows

Windows track recent calls (successes/failures, response times) and provide metrics that trippers use to determine circuit state.

| Window Type | Tracking Method | Use Cases |
|-------------|----------------|-----------|
| **CountWindow** | Last N calls | Fixed call count evaluation |
| **TimeWindow** | Last N seconds | Time-based evaluation, traffic variations |

## CountWindow

Tracks a fixed number of recent calls.

### Basic Usage {#countwindow-basic}

```python
from fluxgate.windows import CountWindow

# Track last 100 calls
window = CountWindow(size=100)
```

### How It Works {#countwindow-how-it-works}

- Maintains only the most recent N calls in memory
- When window is full, evicts the oldest record
- Consistent evaluation even with low call volumes

### Usage Scenarios {#countwindow-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow

# API with stable traffic patterns
cb = CircuitBreaker(
    name="stable_api",
    window=CountWindow(size=100),  # Evaluate last 100 calls
    ...
)
```

## TimeWindow

Tracks calls from the last N seconds based on time.

### Basic Usage {#timewindow-basic}

```python
from fluxgate.windows import TimeWindow

# Track last 60 seconds
window = TimeWindow(size=60)
```

### How It Works {#timewindow-how-it-works}

- Divides time into 1-second buckets
- Each bucket aggregates all calls during that second
- Old buckets automatically expire and are reused

### Usage Scenarios {#timewindow-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import TimeWindow

# API with variable traffic
cb = CircuitBreaker(
    name="variable_traffic_api",
    window=TimeWindow(size=60),  # Evaluate last 60 seconds
    ...
)
```

## Choosing a Window {#choosing-a-window}

### Comparison {#comparison}

| Feature | CountWindow | TimeWindow |
|---------|-------------|------------|
| **Tracking** | Last N calls | Last N seconds |
| **Memory** | Exactly N records | N buckets (1-second each) |
| **Traffic Spikes** | Old data pushed out quickly | Maintains data for consistent duration |
| **Low Traffic** | Fast metric collection | Slower data collection |
| **Evaluation Range** | Varies with traffic patterns | Always consistent (N seconds) |
| **Overhead** | Low | Slightly higher |

### Choose CountWindow {#choose-countwindow}

**Best for:**

- Stable and predictable traffic
- Memory efficiency is important
- Fast metric collection needed

**Examples:** Internal microservice communication, batch jobs

### Choose TimeWindow {#choose-timewindow}

**Best for:**

- Irregular traffic patterns
- Time-based policies needed
- Real-time monitoring is important

**Examples:** Public APIs, user-facing services, external service calls

## Metrics {#metrics}

Both window types provide the same metrics:

```python
from fluxgate.windows import CountWindow
from fluxgate.metric import Record

window = CountWindow(size=100)

# Record calls
window.record(Record(success=True, duration=0.5, timestamp=1234567890.0))
window.record(Record(success=False, duration=1.2, timestamp=1234567891.0))

# Get metrics
metric = window.get_metric()
print(f"Total calls: {metric.total_count}")
print(f"Failed calls: {metric.failure_count}")
print(f"Average duration: {metric.avg_duration}")
```

**Available Metrics:**

- `total_count` - Total number of calls
- `failure_count` - Number of failed calls
- `total_duration` - Total response time
- `slow_count` - Number of slow calls
- `avg_duration` - Average response time (computed property)
- `failure_rate` - Failure rate (computed property)
- `slow_rate` - Slow call rate (computed property)

## Reset {#auto-reset}

Windows are reset when the circuit breaker's state changes.

## Performance Considerations {#performance}

| Operation | CountWindow | TimeWindow |
|-----------|-------------|------------|
| **Memory** | O(N) - N records | O(N) - N buckets (1-second) |
| **record()** | O(1) | O(1) |
| **get_metric()** | O(1) | O(1) |

Both implementations are efficient with negligible overhead in most production environments.

## Next Steps {#next-steps}

- [Trackers](trackers.md) - Define which exceptions to track
- [Trippers](trippers.md) - Control circuit based on window metrics
