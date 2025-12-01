# Circuit Breaker

Circuit Breaker는 분산 시스템에서 실패하는 서비스에 대한 호출을 자동으로 차단하여 연쇄 장애를 방지하는 디자인 패턴입니다.

## 핵심 개념 {#core-concepts}

Circuit Breaker는 전기 회로의 차단기처럼 작동합니다:

- 정상 상태에서는 모든 호출을 허용 (회로가 닫혀있음)
- 실패가 임계값을 초과하면 호출을 차단 (회로가 열림)
- 일정 시간 후 복구를 테스트 (반개방 상태)

## 상태 전환 {#state-transitions}

Circuit Breaker는 6가지 상태를 가집니다:

```text
┌─────────┐           ┌──────┐
│ CLOSED  │──────────>│ OPEN │<─────┐
└─────────┘ [tripper] └──────┘      │
     ^                    │         │
     │                    │[retry]  │[tripper]
     │                    v         │
     │               ┌───────────┐  │
     └───────────────│ HALF_OPEN │──┘
        [!tripper]   └───────────┘
```

### CLOSED (닫힘) {#state-closed}

**정상 작동 상태**

- 모든 호출이 실제 서비스로 전달됨
- 실패 메트릭을 지속적으로 모니터링
- Tripper 조건이 만족되면 OPEN으로 전환

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import All
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=All(),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),  # CLOSED 상태에서만 평가
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)
```

### OPEN (열림) {#state-open}

**호출 차단 상태**

- 모든 호출이 즉시 `CallNotPermittedError` 발생
- 실패한 서비스를 보호하고 리소스 낭비 방지
- Retry 전략에 따라 일정 시간 후 HALF_OPEN으로 전환

```python
from fluxgate.errors import CallNotPermittedError

@cb
def call_api():
    return requests.get("https://api.example.com")

try:
    result = call_api()
except CallNotPermittedError as e:
    print(f"Circuit is open: {e.message}")
    # Fallback 로직 실행
    return {"fallback": "data"}
```

### HALF_OPEN (반개방) {#state-half-open}

**복구 테스트 상태**

- Permit 전략에 따라 제한적으로 호출 허용
- 성공하면 CLOSED로, 실패하면 다시 OPEN으로 전환
- 점진적 복구를 통해 서비스 부담 최소화

```python
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=All(),
    tripper=MinRequests(5) & FailureRate(0.3),  # HALF_OPEN에서는 더 엄격한 기준
    retry=Cooldown(duration=60.0),
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),  # 10%부터 시작하여 점진적 증가
)
```

### METRICS_ONLY (메트릭만) {#state-metrics-only}

**메트릭 수집만 수행**

- 모든 호출이 실제 서비스로 전달됨
- 메트릭은 수집하지만 Circuit은 절대 열리지 않음
- 프로덕션 배포 전 모니터링 테스트에 유용

```python
# 프로덕션 배포 전 메트릭 수집
cb.metrics_only()

# 나중에 실제 Circuit Breaker 활성화
cb.reset()
```

### DISABLED (비활성) {#state-disabled}

**Circuit Breaker 비활성화**

- 모든 호출이 실제 서비스로 전달됨
- 메트릭도 수집하지 않음
- 디버깅이나 긴급 상황에 유용

```python
# 긴급 상황에서 Circuit Breaker 비활성화
cb.disable()

# 나중에 다시 활성화
cb.reset()
```

### FORCED_OPEN (강제 열림) {#state-forced-open}

**강제로 호출 차단**

- 모든 호출이 즉시 `CallNotPermittedError` 발생
- 자동 복구 없음 (수동으로 reset 필요)
- 계획된 유지보수나 긴급 차단에 유용

```python
# 유지보수를 위해 강제로 Circuit 열기
cb.force_open()

# 유지보수 완료 후 복구
cb.reset()
```

## 사용 방법 {#usage}

### 데코레이터 방식 {#decorator-usage}

가장 일반적인 사용 방법입니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import Closed, MinRequests, FailureRate
from fluxgate.retries import Cooldown
from fluxgate.permits import Random

cb = CircuitBreaker(
    name="payment_api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError, TimeoutError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@cb
def charge_payment(amount: float):
    response = requests.post("https://payment.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()
```

### 직접 호출 방식 {#call-usage}

동적으로 함수를 보호해야 할 때 유용합니다.

```python
def process_payment(amount: float):
    response = requests.post("https://payment.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()

# Circuit Breaker를 통해 호출
result = cb.call(process_payment, amount=100.0)
```

### 비동기 지원 {#async-usage}

Asyncio 애플리케이션을 위한 완벽한 지원을 제공합니다.

!!! note
    AsyncCircuitBreaker는 `max_half_open_calls` 파라미터를 통해 HALF_OPEN 상태에서 동시에 실행 가능한 호출 수를 제한합니다. 기본값은 10이며, asyncio.Semaphore를 사용하여 동시성을 제어합니다. 이 제한은 복구 테스트 중인 서비스에 과도한 부하가 가해지는 것을 방지합니다.

```python
import httpx
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    window=CountWindow(size=100),
    tracker=TypeOf(httpx.ConnectError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
    max_half_open_calls=5,  # HALF_OPEN 상태에서 동시 호출 제한 (기본값: 10)
)

@cb
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()

# 사용
result = await fetch_data()
```

## 상태 정보 조회 {#info}

Circuit Breaker의 현재 상태와 메트릭을 확인할 수 있습니다.

```python
info = cb.info()
print(f"Circuit: {info.name}")
print(f"State: {info.state}")
print(f"Changed at: {info.changed_at}")
print(f"Reopens: {info.reopens}")
print(f"Metrics: {info.metrics}")

# 출력 예시:
# Circuit: payment_api
# State: closed
# Changed at: 1234567890.123
# Reopens: 0
# Metrics: Metric(total_count=100, failure_count=5, total_duration=45.2, slow_count=3)
```

## 수동 제어 {#manual-control}

필요시 Circuit Breaker를 수동으로 제어할 수 있습니다.

```python
# CLOSED로 리셋 (메트릭도 초기화)
cb.reset()

# METRICS_ONLY로 전환
cb.metrics_only()

# DISABLED로 전환
cb.disable()

# FORCED_OPEN으로 전환
cb.force_open()

# 리스너에 알림 없이 상태 변경
cb.reset(notify=False)
```

## 에러 처리 {#error-handling}

Circuit이 열려있을 때 발생하는 에러를 처리하는 방법입니다.

### Fallback 파라미터 사용 (권장) {#fallback-parameter}

`fallback` 파라미터를 사용하면 예외 발생 시 자동으로 대체 함수가 호출됩니다.

```python
# fallback 함수는 예외를 인자로 받음
def handle_error(e: Exception) -> dict:
    if isinstance(e, CallNotPermittedError):
        return get_cached_data()  # Circuit 열림
    if isinstance(e, TimeoutError):
        return get_stale_data()   # 타임아웃
    raise e  # 다른 예외는 재발생

@cb(fallback=handle_error)
def api_call() -> dict:
    return requests.get("https://api.example.com").json()

# 사용: 예외 발생 시 자동으로 fallback 호출
result = api_call()
```

### call_with_fallback 사용 {#call-with-fallback}

명시적으로 fallback을 지정하여 호출할 수도 있습니다.

```python
result = cb.call_with_fallback(
    fetch_from_api,
    lambda e: get_cached_data(),
)
```

### 수동 try/except 방식 {#manual-try-except}

```python
from fluxgate.errors import CallNotPermittedError

@cb
def api_call():
    return requests.get("https://api.example.com")

try:
    result = api_call()
except CallNotPermittedError:
    # Circuit이 열려있음 - Fallback 처리
    result = get_cached_data()
except Exception as e:
    # 실제 서비스 에러
    logging.error(f"API call failed: {e}")
    raise
```

## 완전한 예제 {#complete-example}

실제 프로덕션 환경에서 사용할 수 있는 완전한 예제입니다.

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate, SlowRate
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener

# 5xx 에러와 네트워크 실패만 추적
def is_retriable_error(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code >= 500
    return isinstance(e, (httpx.ConnectError, httpx.TimeoutException))

payment_cb = CircuitBreaker(
    name="payment_api",
    window=CountWindow(size=100),
    tracker=Custom(is_retriable_error),
    tripper=MinRequests(20) & (
        (Closed() & (FailureRate(0.6) | SlowRate(0.3))) |    # CLOSED: 60% 실패 또는 30% 느린 호출
        (HalfOpened() & (FailureRate(0.5) | SlowRate(0.2)))  # HALF_OPEN: 50% 실패 또는 20% 느린 호출
    ),
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0,
        jitter_ratio=0.1  # Thundering herd 방지
    ),
    permit=RampUp(
        initial=0.1,      # 10%부터 시작
        final=0.5,        # 50%까지 증가
        duration=60.0     # 60초에 걸쳐
    ),
    listeners=[LogListener(), PrometheusListener()],
    slow_threshold=3.0,  # 3초 이상을 느린 호출로 간주
)

@payment_cb
def charge_payment(amount: float):
    response = httpx.post(
        "https://payment-api.example.com/charge",
        json={"amount": amount},
        timeout=5.0
    )
    response.raise_for_status()
    return response.json()

# 사용
try:
    result = charge_payment(amount=100.0)
    print(f"Payment successful: {result}")
except CallNotPermittedError:
    print("Payment service is temporarily unavailable")
    # Fallback: 결제를 큐에 추가
    queue_payment(amount=100.0)
except httpx.HTTPStatusError as e:
    print(f"Payment failed with status {e.response.status_code}")
    raise
```

## 다음 단계 {#next-steps}

- [Components](components/index.md) - Circuit Breaker를 구성하는 컴포넌트 상세 학습
- [Examples](examples.md) - 실제 사용 패턴과 시나리오
- [API Reference](api/core.md) - 전체 API 문서
