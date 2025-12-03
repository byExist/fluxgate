# Trackers

Trackers are crucial for defining what a "failure" means for your service. While all exceptions are propagated to the caller, a tracker decides which ones should actually count against your error budget and contribute to tripping the circuit breaker. This allows you to distinguish between expected errors (like a 404 Not Found) and actual failures (like a 500 Internal Server Error).

| Tracker Type | Matches Based On... | Best For... |
|---|---|---|
| **All** | Any exception | Simple cases where any exception is a failure. |
| **TypeOf** | The exception's type | When failures can be identified by their type (e.g., `ConnectionError`). |
| **Custom** | A user-defined function | When you need to inspect an exception's content (e.g., an HTTP status code). |

---

## All

This is the simplest tracker. It counts every exception as a failure.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import All

# Any exception raised by the decorated function will be tracked as a failure.
cb = CircuitBreaker(
    name="api",
    tracker=All(),
    ...
)
```

---

## TypeOf

This tracker checks if an exception is an instance of one or more specified types. It's perfect for tracking known, common failure classes.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import TypeOf

# Track only network-related exceptions as failures.
# Other exceptions (e.g., ValueError) will be ignored by the breaker.
cb = CircuitBreaker(
    name="external_api",
    tracker=TypeOf(ConnectionError, TimeoutError),
    ...
)
```

---

## Custom

For maximum flexibility, `Custom` lets you provide your own function to inspect the exception and decide if it's a failure. This is essential for cases where you need to check an exception's attributes, such as an HTTP status code.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import Custom
import httpx

# Only count 5xx server errors as failures. Client errors (4xx) will be ignored.
def is_server_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return False

cb = CircuitBreaker(
    name="http_api",
    tracker=Custom(is_server_error),
    ...
)
```

---

## Combining Trackers with Logical Operators {#operators}

The real power of trackers comes from combining them with logical operators (`&`, `|`, `~`) to create precise failure-detection rules.

### AND (`&`)

Use the `&` operator to create a tracker that matches only if **both** conditions are true.

```python
from fluxgate.trackers import TypeOf, Custom

# Track ConnectionError exceptions that also contain the word "timeout".
tracker = (
    TypeOf(ConnectionError) &
    Custom(lambda e: "timeout" in str(e).lower())
)
```

### OR (`|`)

Use the `|` operator to create a tracker that matches if **either** condition is true.

```python
from fluxgate.trackers import TypeOf

# Track either a ConnectionError OR a TimeoutError.
tracker = TypeOf(ConnectionError) | TypeOf(TimeoutError)

# This is equivalent to passing multiple types to TypeOf directly.
tracker = TypeOf(ConnectionError, TimeoutError)
```

### NOT (`~`)

Use the `~` operator to **invert** a condition, excluding certain errors.

```python
from fluxgate.trackers import TypeOf, Custom
import httpx

# Ignore 4xx client errors, but track all other HTTPStatusError exceptions (e.g., 5xx).
is_4xx_error = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500)
tracker = TypeOf(httpx.HTTPStatusError) & ~is_4xx_error
```

### Complex Example

You can combine these operators to build sophisticated rules.

```python
from fluxgate.trackers import TypeOf, Custom
import httpx

# This tracker counts an exception as a failure if:
# 1. It is a network error (ConnectionError or TimeoutError), OR
# 2. It is a 5xx server error, AND
# 3. It is NOT a 401 Unauthorized error (which we might handle differently).

network_errors = TypeOf(ConnectionError, TimeoutError)
server_errors = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
is_auth_error = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401)

tracker = (network_errors | server_errors) & ~is_auth_error
```

---

## Choosing the Right Tracker

### Comparison {#comparison}

| Feature | All | TypeOf | Custom |
|---|---|---|---|
| **Simplicity** | Dead simple | Simple | Requires a custom function |
| **Flexibility** | Low | Medium | High |
| **Performance** | Excellent (O(1)) | Excellent (O(1)) | Depends on your function |
| **Primary Use** | Track everything | Track specific types | Inspect exception contents |

### When should I use `All`? {#choose-all}

`All` is best when any exception indicates a genuine failure. It's often combined with `~` to exclude a few specific, expected exceptions.

- **Use case**: Protecting an internal service where any error is considered critical.

### When should I use `TypeOf`? {#choose-typeof}

`TypeOf` is the most common choice for tracking failures from external services where you can anticipate the kinds of errors that occur.

- **Use case**: Calling an external API where you expect `TimeoutError` or `ConnectionError`.

### When should I use `Custom`? {#choose-custom}

`Custom` is necessary when you need to look inside an exception to decide if it's a failure.

- **Use case**: Checking the status code of an `httpx.HTTPStatusError` to distinguish between client errors (4xx) and server errors (5xx).

## Next Steps {#next-steps}

- [Windows](windows.md): Learn how call history is stored.
- [Trippers](trippers.md): Use the metrics gathered by trackers to build tripping logic.
