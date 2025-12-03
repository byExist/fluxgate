# Tracker

Tracker는 "실패"가 무엇을 의미하는지 정의합니다. 모든 예외는 호출자에게 전파되지만, Tracker는 어떤 예외가 실제로 실패로 취급되어 Circuit Breaker를 trip 시키는 데 기여해야 하는지 결정합니다. 이를 통해 예상된 오류(예: 404 Not Found)와 실제 실패(예: 500 Internal Server Error)를 구별할 수 있습니다.

| Tracker 유형 | 일치 기준 | 적합한 경우 |
|---|---|---|
| **All** | 모든 예외 | 모든 예외를 실패로 취급하는 경우. |
| **TypeOf** | 예외 유형 | 예외 유형으로 실패를 식별할 수 있는 경우. (예: `ConnectionError`) |
| **Custom** | 사용자 정의 함수 | 실패로 취급할 조건을 사용자 정의하고자 하는 경우. (예: HTTP Status Code) |

---

## All

가장 간단한 Tracker입니다. 모든 예외를 실패로 간주합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import All

# 데코레이터가 적용된 함수에서 발생하는 모든 예외는 실패로 추적됩니다.
cb = CircuitBreaker(
    name="api",
    tracker=All(),
    ...
)
```

---

## TypeOf

이 Tracker는 예외가 하나 이상의 지정된 유형의 인스턴스인지 확인합니다. 예외 유형을 특정할 수 있을 때 유용합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import TypeOf

# 네트워크 관련 예외만 실패로 추적합니다.
# 다른 예외(예: ValueError)는 Circuit Breaker 상태 전환 조건에서 활용되지 않습니다.
cb = CircuitBreaker(
    name="external_api",
    tracker=TypeOf(ConnectionError, TimeoutError),
    ...
)
```

---

## Custom

최대한의 유연성을 위해 `Custom`은 예외를 검사하고 실패 여부를 결정하는 자체 함수를 제공할 수 있도록 합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import Custom
import httpx

# 5xx 서버 오류만 실패로 간주합니다. 클라이언트 오류(4xx)는 무시됩니다.
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

## 논리 연산자로 Tracker 조합 {#operators}

Tracker는 논리 연산자(&, \|, ~)를 지원하며, 정확한 실패 감지 규칙을 정의할 수 있습니다.

### AND (`&`)

`&` 연산자를 사용하여 **두** 조건이 모두 참인 경우에만 일치하는 Tracker를 만듭니다.

```python
from fluxgate.trackers import TypeOf, Custom

# ConnectionError 예외이면서 "timeout"이라는 단어를 포함하는 경우를 추적합니다.
tracker = (
    TypeOf(ConnectionError) &
    Custom(lambda e: "timeout" in str(e).lower())
)
```

### OR (`|`)

`|` 연산자를 사용하여 **어느 한** 조건이 참인 경우에 일치하는 Tracker를 만듭니다.

```python
from fluxgate.trackers import TypeOf

# ConnectionError 또는 TimeoutError 중 하나를 추적합니다.
tracker = TypeOf(ConnectionError) | TypeOf(TimeoutError)

# 이는 TypeOf에 여러 유형을 직접 전달하는 것과 동일합니다.
tracker = TypeOf(ConnectionError, TimeoutError)
```

### NOT (`~`)

`~` 연산자를 사용하여 조건을 **반전**시켜 특정 오류를 제외합니다.

```python
from fluxgate.trackers import TypeOf, Custom
import httpx

# 4xx 클라이언트 오류를 무시하고, 다른 모든 HTTPStatusError 예외(예: 5xx)를 추적합니다.
is_4xx_error = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500)
tracker = TypeOf(httpx.HTTPStatusError) & ~is_4xx_error
```

### 복합 예제

이러한 연산자를 조합하여 정교한 규칙을 만들 수 있습니다.

```python
from fluxgate.trackers import TypeOf, Custom
import httpx

# 이 Tracker는 다음 경우에 예외를 실패로 간주합니다.
# 1. 네트워크 오류(ConnectionError 또는 TimeoutError)이거나, 또는
# 2. 5xx 서버 오류이고, 그리고
# 3. 401 Unauthorized 오류가 아닌 경우(이것은 다르게 처리할 수 있음).

network_errors = TypeOf(ConnectionError, TimeoutError)
server_errors = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
is_auth_error = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401)

tracker = (network_errors | server_errors) & ~is_auth_error
```

---

## 올바른 Tracker 선택

### 비교 {#comparison}

| 기능 | All | TypeOf | Custom |
|---|---|---|---|
| **단순성** | 매우 간단 | 간단 | 사용자 정의 함수 필요 |
| **유연성** | 낮음 | 중간 | 높음 |
| **성능** | O(1) | O(1) | 함수에 따라 다름 |
| **주요 용도** | 모든 것을 추적 | 특정 유형 추적 | 예외 내용 검사 |

### `All`은 언제 사용해야 하나요? {#choose-all}

`All`은 모든 예외를 실패로 취급합니다.

- **사용 사례**: 모든 오류가 중요하다고 간주되는 내부 서비스 보호.

### `TypeOf`은 언제 사용해야 하나요? {#choose-typeof}

`TypeOf`은 외부 서비스에서 발생하는 오류 유형을 예상할 수 있을 때 실패를 추적하는 가장 일반적인 선택입니다.

- **사용 사례**: `TimeoutError` 또는 `ConnectionError`를 예상하는 외부 API 호출.

### `Custom`은 언제 사용해야 하나요? {#choose-custom}

`Custom`은 실패 여부를 사용자 설정으로 제어하고자 할 때 유용합니다.

- **사용 사례**: `httpx.HTTPStatusError`의 상태 코드를 확인하여 클라이언트 오류(4xx)와 서버 오류(5xx)를 구별합니다.

## 다음 단계 {#next-steps}

- [Windows](windows.md): 호출 기록이 어떻게 저장되는지 알아보세요.
- [Trippers](trippers.md): Tracker가 수집한 Metric을 사용하여 Trip 로직을 구축하세요.
