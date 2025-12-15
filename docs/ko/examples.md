# 예제

이 페이지는 Fluxgate를 시작하는 데 도움이 되는 실용적인 실제 예제를 제공합니다.

---

## 1. 외부 API 호출 보호

가장 일반적인 사용 사례입니다. 목표는 느리거나 실패하는 외부 서비스로부터 애플리케이션을 보호하는 것입니다.

기본 설정으로 Fluxgate는 다음을 수행합니다:

- 마지막 100개 호출에 대한 실패 추적
- 50% 실패율에서 트립 (최소 100회 호출 후)
- 복구 전 60초 대기
- 복구 중 50%의 호출 허용

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.trackers import TypeOf

cb = CircuitBreaker(
    name="payment_api",
    tracker=TypeOf(httpx.HTTPError),  # HTTP 에러만 추적
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

---

## 2. 웹 프레임워크와 통합 (FastAPI)

웹 프레임워크와 통합할 때, 일반적으로 `CallNotPermittedError`를 잡아서 `503 Service Unavailable`과 같은 사용자 친화적인 오류 응답을 반환하고 싶을 것입니다.

<!--pytest.mark.skip-->

```python
from fastapi import FastAPI, HTTPException
import httpx
from fluxgate import AsyncCircuitBreaker, CallNotPermittedError
from fluxgate.trackers import TypeOf
from fluxgate.retries import Cooldown

app = FastAPI()

# 중요한 외부 서비스를 위한 단일 circuit breaker.
external_api_cb = AsyncCircuitBreaker(
    name="external_product_api",
    tracker=TypeOf(httpx.HTTPError),
    retry=Cooldown(duration=30.0),  # 더 빠른 복구를 위해 짧은 쿨다운
)

# 핵심 로직을 위한 별도의 함수가 좋은 관행입니다.
@external_api_cb
async def fetch_product_data(product_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/products/{product_id}")
        response.raise_for_status()
        return response.json()

@app.get("/products/{product_id}")
async def get_product(product_id: str):
    try:
        data = await fetch_product_data(product_id)
        return data
    except CallNotPermittedError:
        # 회로가 열려 있으므로 503 오류를 반환합니다.
        raise HTTPException(
            status_code=503,
            detail="외부 제품 서비스를 현재 사용할 수 없습니다. 나중에 다시 시도하십시오."
        )
    except httpx.HTTPStatusError as e:
        # 외부 서비스가 오류를 반환했습니다.
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
```

---

## 3. 서비스별로 다른 정책 적용

서로 다른 외부 서비스에 대해 각각 자체적으로 조정된 정책을 가진 다른 circuit breaker를 사용하는 것이 일반적입니다. 결제와 같은 중요한 서비스는 인벤토리와 같은 덜 중요한 서비스보다 더 보수적인 구성을 가질 수 있습니다.

```python
import httpx
from fluxgate import AsyncCircuitBreaker
from fluxgate.windows import TimeWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import MinRequests, FailureRate, FailureStreak
from fluxgate.retries import Backoff

# 중요한 결제 서비스에 대한 더 보수적인 정책.
# FailureStreak은 MinRequests가 충족되기 전 콜드 스타트 시 빠른 보호를 제공합니다.
payment_cb = AsyncCircuitBreaker(
    name="payment_service",
    window=TimeWindow(size=300),
    tracker=TypeOf(httpx.HTTPError),
    tripper=FailureStreak(5) | (MinRequests(20) & FailureRate(0.4)),
    retry=Backoff(initial=30.0, max_duration=600.0),
)

# 덜 중요한 인벤토리 서비스에 대한 더 공격적인 정책.
inventory_cb = AsyncCircuitBreaker(
    name="inventory_service",
    window=TimeWindow(size=60),
    tracker=TypeOf(httpx.HTTPError),
    tripper=MinRequests(10) & FailureRate(0.6),
    retry=Backoff(initial=10.0, max_duration=300.0),
)

@payment_cb
async def charge_payment(amount: float):
    pass

@inventory_cb
async def check_inventory(product_id: str):
    pass
```

---

## 4. Fallback 처리

호출이 차단되거나 실패하면 캐시된 데이터를 반환하는 것과 같은 대체 로직을 실행하는 경우가 많습니다. 이를 "폴백"이라고 합니다.

### `fallback` 데코레이터 인자 사용 (권장)

이것이 가장 깔끔한 접근 방식입니다. 보호된 함수가 **어떤** 예외를 발생시키든 제공된 함수가 자동으로 호출됩니다. 폴백 함수는 예외 인스턴스를 받으므로 어떻게 처리할지 결정할 수 있습니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker, CallNotPermittedError

# 캐시에서 데이터를 가져오는 함수에 대한 플레이스홀더.
def get_cached_data(e: Exception):
    print(f"다음으로 인해 캐시된 데이터 반환: {type(e).__name__}")
    return {"source": "cache"}

# fetch_from_api가 예외를 발생시키는 경우에만 폴백이 호출됩니다.
@cb(fallback=get_cached_data)
def fetch_data_with_fallback() -> dict:
    # ... 라이브 API에서 가져오는 로직 ...
    raise httpx.ConnectError("연결 실패!")

# 사용: 폴백이 자동으로 호출됩니다.
result = fetch_data_with_fallback() # {"source": "cache"} 반환
```

### `call_with_fallback` 사용

데코레이터를 사용할 수 없을 때 유용합니다. `fallback` 인자와 동일하게 작동합니다.

<!--pytest.mark.skip-->

```python
def fetch_from_api():
    # ...
    pass

# fetch_from_api가 예외를 발생시키는 경우에만 폴백이 호출됩니다.
result = cb.call_with_fallback(
    fetch_from_api,
    fallback_func=get_cached_data,
)
```

### 수동 `try...except`

최대한의 제어를 위해 표준 `try...except` 블록을 사용할 수 있습니다. 이는 최대한의 유연성을 제공하지만 더 장황합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CallNotPermittedError

@cb
def fetch_data():
    # ...
    pass

try:
    result = fetch_data()
except CallNotPermittedError as e:
    # 이 블록은 회로가 열려 있을 때만 실행됩니다.
    print("회로가 열렸습니다. 폴백을 반환합니다.")
    result = get_cached_data(e)
except httpx.HTTPError as e:
    # 이 블록은 다른 특정 오류 발생 시 실행됩니다.
    print(f"API 호출 실패: {e}, 폴백 반환.")
    result = get_cached_data(e)
```

---

## 5. 고급 구성 패턴

### 사용자 정의 오류 추적

`tracker`를 사용하면 실패로 간주되는 요소를 정확하게 정의할 수 있습니다. 예를 들어, 5xx 서버 오류를 추적하면서 4xx 클라이언트 오류는 무시할 수 있습니다.

<!--pytest.mark.skip-->

```python
import httpx
from fluxgate.trackers import Custom

# 이 함수는 추적하려는 오류에 대해서만 True를 반환합니다.
def is_retriable_server_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        # 5xx 오류는 실패이지만, 4xx 오류는 실패가 아닙니다.
        return e.response.status_code >= 500
    # 또한 네트워크 오류도 추적합니다.
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

cb = CircuitBreaker(
    name="api_client",
    tracker=Custom(is_retriable_server_error),
    ...
)
```

### 상태별 다른 임계값

`Closed()` 및 `HalfOpened()` Tripper를 사용하여 복구 시도에 대한 더 엄격한 규칙을 만들 수 있습니다.

<!--pytest.mark.skip-->

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

cb = CircuitBreaker(
    name="api",
    # CLOSED 및 HALF_OPEN 상태에 대해 다른 트립 조건을 사용합니다.
    tripper=(
        (Closed() & MinRequests(20) & FailureRate(0.6)) |
        (HalfOpened() & MinRequests(5) & FailureRate(0.5)) # 더 엄격하게
    ),
    ...
)
```

### 동적 생성을 위한 팩토리

팩토리 함수는 코드를 반복하지 않고도 많은 유사한 circuit breaker를 생성하고 관리하기 위한 강력한 패턴입니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Cooldown
from fluxgate.windows import CountWindow
from fluxgate.trippers import MinRequests, FailureRate

def circuit_breaker_factory(name: str, policy: str) -> CircuitBreaker:
    """정의된 정책 이름에 따라 circuit breaker를 생성합니다."""
    if policy == "strict":
        return CircuitBreaker(
            name=name,
            tripper=MinRequests(20) & FailureRate(0.4),
        )
    elif policy == "lenient":
        return CircuitBreaker(
            name=name,
            window=CountWindow(50),
            tripper=MinRequests(10) & FailureRate(0.7),
            retry=Cooldown(30.0),
        )
    else:
        raise ValueError(f"알 수 없는 정책: {policy}")

# 즉시 브레이커 생성
checkout_cb = circuit_breaker_factory("checkout", "strict")
recommendation_cb = circuit_breaker_factory("recommendations", "lenient")
```

## 다음 단계

- [컴포넌트 개요](components/index.md): 각 컴포넌트에 대해 더 깊이 알아보세요.
- [Listener 개요](components/listeners/index.md): circuit breaker를 모니터링하는 방법을 배우세요.
- [API 레퍼런스](api/core.md): 전체 API 문서를 살펴보세요.
