# Trackers

Tracker는 발생한 예외를 circuit breaker가 실패로 기록할지 판단합니다. 모든 예외는 호출자에게 전파되며, 실패로 기록된 예외만 메트릭에 반영됩니다.

| Tracker 타입 | 매칭 방식 | 사용 사례 |
|-------------|----------|----------|
| **All** | 모든 예외 | 모든 실패 추적 |
| **TypeOf** | 예외 타입 | 특정 예외만 추적 |
| **Custom** | 사용자 정의 함수 | 복잡한 조건 |

## All

모든 예외를 실패로 추적합니다.

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

특정 타입의 예외만 실패로 추적합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import TypeOf

# 네트워크 관련 예외만 추적
cb = CircuitBreaker(
    name="external_api",
    tracker=TypeOf(ConnectionError, TimeoutError),
    ...
)
```

## Custom

사용자 정의 함수로 예외를 판별합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trackers import Custom
import httpx

# HTTP 5xx 에러만 추적
def is_server_error(e: Exception) -> bool:
    return isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500

cb = CircuitBreaker(
    name="http_api",
    tracker=Custom(is_server_error),
    ...
)
```

## 논리 연산자 {#operators}

Tracker는 논리 연산자로 조합할 수 있습니다.

### AND (`&`) - 두 조건 모두 만족

```python
from fluxgate.trackers import TypeOf

# ConnectionError이면서 특정 메시지를 포함하는 경우
tracker = (
    TypeOf(ConnectionError) &
    Custom(lambda e: "timeout" in str(e).lower())
)
```

### OR (`|`) - 둘 중 하나 만족

```python
from fluxgate.trackers import TypeOf

# ConnectionError 또는 TimeoutError
tracker = TypeOf(ConnectionError) | TypeOf(TimeoutError)

# 또는 한 번에 지정
tracker = TypeOf(ConnectionError, TimeoutError)
```

### NOT (`~`) - 조건 반전

```python
from fluxgate.trackers import Custom
import httpx

# HTTP 에러 중 4xx 제외 (5xx만 추적)
is_4xx = lambda e: isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500
tracker = TypeOf(httpx.HTTPStatusError) & ~Custom(is_4xx)
```

### 복잡한 조합

```python
from fluxgate.trackers import TypeOf, Custom
import httpx

# (네트워크 에러 또는 5xx 에러) 그리고 재시도 가능
network_errors = TypeOf(ConnectionError, TimeoutError)
server_errors = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
not_auth_error = ~Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 401)

tracker = (network_errors | server_errors) & not_auth_error
```

## 선택 가이드 {#choosing-a-tracker}

### 비교 {#comparison}

| 특성 | All | TypeOf | Custom |
|-----|-----|--------|--------|
| **간결성** | 가장 단순 | 단순 | 함수 작성 필요 |
| **유연성** | 낮음 | 중간 | 높음 |
| **성능** | O(1) | O(1) | 함수에 따라 다름 |
| **사용 사례** | 모든 실패 추적 | 타입별 추적 | 복잡한 조건 |

### All을 선택하세요 {#choose-all}

**적합한 경우:**

- 모든 예외를 실패로 간주
- 단순한 에러 핸들링
- 특정 예외만 제외하고 싶을 때 (논리 연산자 조합)

**예시:** 단순한 내부 서비스, 모든 에러가 중요한 경우

### TypeOf를 선택하세요 {#choose-typeof}

**적합한 경우:**

- 특정 타입의 예외만 추적
- 네트워크, 타임아웃 등 예측 가능한 에러
- 타입으로 분류 가능한 실패

**예시:** 외부 API 호출, 네트워크 의존 서비스

### Custom을 선택하세요 {#choose-custom}

**적합한 경우:**

- HTTP 상태 코드 기반 판별
- 예외 메시지나 속성 검사
- 복잡한 비즈니스 로직

**예시:** HTTP API, 조건부 재시도, 세밀한 에러 분류

## 다음 단계 {#next-steps}

- [Trippers](trippers.md) - Tracker가 수집한 메트릭을 기반으로 circuit 제어
- [Windows](windows.md) - 실패 추적 방식 결정
