# Trackers

Trackers determine whether raised exceptions should be recorded as failures by the circuit breaker. All exceptions propagate to the caller, but only recorded exceptions affect metrics.

| Tracker Type | Matching | Use Case |
|--------------|----------|----------|
| **All** | All exceptions | Track all failures |
| **TypeOf** | Exception type | Track specific exceptions |
| **Custom** | Custom function | Complex conditions |

## All

Tracks all exceptions as failures.

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import All

cb = CircuitBreaker(
    name="api",
    tracker=All(),
    ...
)
```

## TypeOf

Tracks only exceptions of specific types.

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import TypeOf

# Track only network-related exceptions
cb = CircuitBreaker(
    name="external_api",
    tracker=TypeOf(ConnectionError, TimeoutError),
    ...
)
```

## Custom

Uses custom function to determine exceptions.

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import Custom
import httpx

# Track only HTTP 5xx errors
def is_server_error(e: Exception) -> bool:
    return isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500

cb = CircuitBreaker(
    name="http_api",
    tracker=Custom(is_server_error),
    ...
)
```

## Logical Operators {#operators}

Trackers can be combined with logical operators.

### AND (`&`) - Both Conditions

```python
from fluxgate.trackers import TypeOf

# ConnectionError AND contains specific message
tracker = (
    TypeOf(ConnectionError) &
    Custom(lambda e: "timeout" in str(e).lower())
)
```

### OR (`|`) - Either Condition

```python
from fluxgate.trackers import TypeOf

# ConnectionError OR TimeoutError
tracker = TypeOf(ConnectionError) | TypeOf(TimeoutError)

# Or specify at once
tracker = TypeOf(ConnectionError, TimeoutError)
```

### NOT (`~`) - Invert Condition

```python
from fluxgate.trackers import Custom
import httpx

# HTTP errors excluding 4xx (track only 5xx)
is_4xx = lambda e: isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500
tracker = TypeOf(httpx.HTTPStatusError) & ~Custom(is_4xx)
```

### Complex Combinations

```python
from fluxgate.trackers import TypeOf, Custom
import httpx

# (Network errors OR 5xx errors) AND retriable
network_errors = TypeOf(ConnectionError, TimeoutError)
server_errors = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
not_auth_error = ~Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401)

tracker = (network_errors | server_errors) & not_auth_error
```

## Choosing a Tracker {#choosing-a-tracker}

### Comparison {#comparison}

| Feature | All | TypeOf | Custom |
|---------|-----|--------|--------|
| **Simplicity** | Simplest | Simple | Requires function |
| **Flexibility** | Low | Medium | High |
| **Performance** | O(1) | O(1) | Depends on function |
| **Use Case** | Track all failures | Track by type | Complex conditions |

### Choose All {#choose-all}

**Best for:**

- Treating all exceptions as failures
- Simple error handling
- Excluding specific exceptions (with logical operators)

**Examples:** Simple internal services, all errors are critical

### Choose TypeOf {#choose-typeof}

**Best for:**

- Tracking specific exception types
- Predictable errors like network, timeout
- Failures classifiable by type

**Examples:** External API calls, network-dependent services

### Choose Custom {#choose-custom}

**Best for:**

- HTTP status code-based matching
- Inspecting exception messages or attributes
- Complex business logic

**Examples:** HTTP APIs, conditional retries, fine-grained error classification

## Next Steps {#next-steps}

- [Trippers](trippers.md) - Control circuit based on metrics collected by trackers
- [Windows](windows.md) - Determine failure tracking approach
