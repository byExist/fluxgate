# Examples

실제 사용 사례로 Fluxgate를 빠르게 시작하세요.

## 기본 사용법

### HTTP API 보호

외부 API 호출을 Circuit Breaker로 보호합니다.

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="payment_api",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@cb
def charge_payment(amount: float):
    response = httpx.post(
        "https://api.example.com/charge",
        json={"amount": amount}
    )
    response.raise_for_status()
    return response.json()
```

## 비동기 사용법

### FastAPI 통합

FastAPI 엔드포인트에 Circuit Breaker를 적용합니다.

```python
from fastapi import FastAPI, HTTPException
import httpx
from fluxgate import AsyncCircuitBreaker, CallNotPermittedError
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

app = FastAPI()

cb = AsyncCircuitBreaker(
    name="external_api",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@app.get("/data")
async def get_data():
    try:
        @cb
        async def fetch():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                response.raise_for_status()
                return response.json()

        return await fetch()
    except CallNotPermittedError:
        raise HTTPException(status_code=503, detail="Service unavailable")
```

### 여러 Circuit Breaker 관리

서비스별로 독립적인 Circuit Breaker를 생성합니다.

```python
import httpx
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

# 서비스별 Circuit Breaker
payment_cb = AsyncCircuitBreaker(
    name="payment_service",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

inventory_cb = AsyncCircuitBreaker(
    name="inventory_service",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.HTTPError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.3),
    retry=Cooldown(duration=30.0),
    permit=Random(ratio=0.7),
)

@payment_cb
async def charge_payment(amount: float):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://payment.example.com/charge",
            json={"amount": amount}
        )
        response.raise_for_status()
        return response.json()

@inventory_cb
async def check_inventory(product_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://inventory.example.com/products/{product_id}"
        )
        response.raise_for_status()
        return response.json()
```

## 고급 사용법

### 커스텀 에러 추적

특정 조건의 에러만 Circuit Breaker에서 추적합니다.

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

# 5xx 에러와 네트워크 장애만 추적
def is_server_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

cb = CircuitBreaker(
    name="api_client",
    window=CountWindow(size=100),
    tracker=Custom(is_server_error),
    tripper=Closed() & MinRequests(20) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)
```

### 상태별 서로 다른 임계값

CLOSED와 HALF_OPEN 상태에서 다른 임계값을 적용합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    # CLOSED: 60% 실패율, HALF_OPEN: 50% 실패율
    tripper=MinRequests(20) & (
        (Closed() & FailureRate(0.6)) |
        (HalfOpened() & FailureRate(0.5))
    ),
    retry=Cooldown(duration=60.0),
    # 점진적 트래픽 증가: 10% → 80% (60초)
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
)
```

### Fallback 처리 {#fallback}

Circuit이 열렸을 때 대체 동작을 수행합니다. `fallback` 파라미터를 사용하면 예외 발생 시 자동으로 대체 함수가 호출됩니다.

#### 데코레이터에서 fallback 사용

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

# fallback 함수는 예외를 인자로 받음
def fallback_handler(e: Exception) -> dict:
    if isinstance(e, ConnectionError):
        return get_cached_data()
    raise e  # 다른 예외는 재발생

@cb(fallback=fallback_handler)
def fetch_data() -> dict:
    return fetch_from_api()

# 사용: Circuit이 열려있거나 에러 발생 시 자동으로 fallback 호출
result = fetch_data()
```

#### call_with_fallback 사용

명시적으로 fallback을 지정하여 호출할 수도 있습니다.

```python
# 함수와 fallback을 함께 전달
result = cb.call_with_fallback(
    fetch_from_api,
    lambda e: get_cached_data(),
)

# 인자가 있는 함수
result = cb.call_with_fallback(
    fetch_user_data,
    lambda e: {"user_id": user_id, "cached": True},
    user_id,  # 원본 함수에 전달될 인자
)
```

#### 비동기 fallback

AsyncCircuitBreaker에서도 동일하게 사용합니다.

```python
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    # ... 설정
)

@cb(fallback=lambda e: {"status": "fallback"})
async def fetch_data() -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# 또는 call_with_fallback
result = await cb.call_with_fallback(
    fetch_from_api,
    lambda e: get_cached_data(),
)
```

#### 수동 try/except 방식 (기존 방식)

fallback 없이 직접 예외를 처리할 수도 있습니다.

```python
from fluxgate import CallNotPermittedError

@cb
def fetch():
    return fetch_from_api()

try:
    result = fetch()
except CallNotPermittedError:
    # Circuit이 열려있을 때
    result = get_cached_data()
except ConnectionError:
    # 연결 실패 시
    result = get_cached_data()
```

### 팩토리 함수

엔드포인트별로 다른 정책의 Circuit Breaker를 생성합니다.

```python
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate, SlowRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random
import httpx

def create_payment_circuit_breaker(
    endpoint: str,
    slow_threshold: float,
    failure_rate: float = 0.5,
    slow_rate: float = 0.5,
) -> AsyncCircuitBreaker:
    return AsyncCircuitBreaker(
        name=f"payment_{endpoint}",
        window=CountWindow(size=100),
        tracker=TypeOf(httpx.HTTPError),
        tripper=Closed() & MinRequests(10) & (
            FailureRate(failure_rate) | SlowRate(slow_rate, slow_threshold)
        ),
        retry=Cooldown(duration=60.0),
        permit=Random(ratio=0.5),
    )

# 변수에 저장
charge_cb = create_payment_circuit_breaker("charge", slow_threshold=2.0, failure_rate=0.3)
refund_cb = create_payment_circuit_breaker("refund", slow_threshold=3.0, failure_rate=0.3)
history_cb = create_payment_circuit_breaker("history", slow_threshold=0.5)

# 또는 바로 데코레이터로 사용
@create_payment_circuit_breaker("charge", slow_threshold=2.0, failure_rate=0.3)
async def charge_payment(amount: float):
    ...
```

## 다음 단계

- [Components](components/index.md) - 상세 컴포넌트 문서
- [Listeners](components/listeners/index.md) - 모니터링 및 알림 설정
- [API Reference](api/core.md) - 전체 API 문서
