# Fluxgate

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/byExist/fluxgate/blob/master/LICENSE)

동기 및 비동기 코드를 모두 완벽하게 지원하는 Python용 현대적이고 조합 가능한 Circuit Breaker 라이브러리입니다.

## 왜 Fluxgate인가?

Circuit breaker는 서비스 상태를 모니터링하고 실패하는 서비스에 대한 호출을 일시적으로 차단하여 분산 시스템의 연쇄 장애를 방지합니다. Fluxgate는 이를 쉽게 만들어줍니다:

- **동기 & 비동기**: 동기 및 비동기 코드 모두 완벽 지원
- **조합 가능**: 간단하고 재사용 가능한 컴포넌트로 복잡한 실패 감지 로직 구성
- **의존성 없음**: 코어 라이브러리는 외부 의존성 없음
- **완전한 타입 힌팅**: IDE 지원을 위한 완벽한 타입 힌트
- **프로덕션 준비 완료**: Prometheus, Slack, 로깅을 통한 내장 모니터링

## 빠른 시작

### 설치

```bash
pip install fluxgate
```

### 기본 예제

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
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
)

@cb
def call_payment_api(amount: float):
    return requests.post("https://api.example.com/pay", json={"amount": amount})
```

### 작동 방식

Circuit breaker는 세 가지 주요 상태로 작동합니다:

```text
CLOSED --[tripper]--> OPEN --[retry]--> HALF_OPEN --[!tripper]--> CLOSED
                       ^                   |
                       +----[tripper]------+
```

- **CLOSED**: 정상 동작, 모든 호출 허용
- **OPEN**: 실패 임계값 초과, 호출 차단
- **HALF_OPEN**: 복구 테스트 중, 제한적 호출 허용

## 핵심 컴포넌트

Fluxgate는 조합 가능한 컴포넌트를 사용하여 유연한 실패 감지 로직을 구축합니다:

| 컴포넌트 | 목적 | 예제 |
|---------|------|------|
| **Windows** | 호출 기록 추적 | `CountWindow(100)` - 최근 100개 호출 |
|  |  | `TimeWindow(60)` - 최근 60초 |
| **Trackers** | 추적할 항목 정의 | `TypeOf(ConnectionError)` - 특정 에러 추적 |
|  |  | `Custom(func)` - 커스텀 로직 |
| **Trippers** | circuit 열 시점 | `FailureRate(0.5)` - 50% 실패율 |
|  |  | `AvgLatency(2.0)` - 느린 응답 |
| **Retries** | 재시도 시점 | `Cooldown(60.0)` - 60초 대기 |
|  |  | `Backoff(10.0)` - 지수 백오프 |
| **Permits** | 복구 제어 | `Random(0.5)` - 50% 호출 허용 |
|  |  | `RampUp(0.1, 0.8, 60)` - 점진적 증가 |

## 비동기 지원

Asyncio 애플리케이션을 완벽하게 지원합니다:

```python
from fluxgate import AsyncCircuitBreaker

cb = AsyncCircuitBreaker(
    name="async_api",
    window=CountWindow(size=100),
    tracker=TypeOf(ConnectionError),
    tripper=Closed() & MinRequests(10) & FailureRate(0.5),
    retry=Cooldown(duration=60.0),
    permit=Random(ratio=0.5),
    max_half_open_calls=5,
)

@cb
async def call_async_api():
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com/data")
```

## 프로덕션 예제

외부 결제 API를 위한 프로덕션 준비 완료 circuit breaker:

```python
import httpx
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate
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
        (Closed() & FailureRate(0.6)) |
        (HalfOpened() & FailureRate(0.5))
    ),
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0, jitter_ratio=0.1),
    permit=RampUp(initial=0.1, final=0.5, duration=60.0),
    listeners=[LogListener(), PrometheusListener()],
)

@payment_cb
def charge_payment(amount: float):
    response = httpx.post("https://payment-api.example.com/charge", json={"amount": amount})
    response.raise_for_status()
    return response.json()
```

## 다음 단계

- [컴포넌트](components/index.md) 알아보기 - Windows, Trackers, Trippers, Retries, Permits 심화 학습
- [예제](examples.md) 보기 - 실제 사용 패턴
- [API 레퍼런스](api/core.md) 읽기 - 완전한 API 문서
