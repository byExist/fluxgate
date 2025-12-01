# 컴포넌트 개요 {#components-overview}

Fluxgate는 조합 가능한 컴포넌트를 사용하여 유연한 circuit breaker 설정을 구축합니다. 각 컴포넌트는 circuit breaker 동작의 특정 측면을 담당합니다.

## 아키텍처 {#architecture}

| 컴포넌트 | 역할 | 지원 연산자 |
|---------|------|-----------|
| **Window** | 호출 기록 추적 (개수 또는 시간 기반) | - |
| **Tracker** | 추적할 예외 정의 | &, \|, ~ |
| **Tripper** | Circuit을 여닫는 조건 결정 | &, \| |
| **Retry** | OPEN → HALF_OPEN 전환 시점 제어 | - |
| **Permit** | HALF_OPEN 상태에서 호출 허용 여부 결정 | - |
| **Listener** | 상태 전환 감지 및 외부 시스템 알림 | - |

## 컴포넌트 타입 {#component-types}

### [Windows](windows.md)

슬라이딩 윈도우를 통해 호출 기록을 추적합니다.

- **CountWindow** - 최근 N개 호출
- **TimeWindow** - 최근 N초

```python
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # 최근 100개 호출 추적
window = TimeWindow(size=60)    # 최근 60초 추적
```

### [Trackers](trackers.md) {#trackers}

어떤 예외를 실패로 간주할지 정의합니다.

- **All** - 모든 예외 추적
- **TypeOf** - 특정 예외 타입 추적
- **Custom** - 커스텀 추적 로직

```python
from fluxgate.trackers import TypeOf, Custom

tracker = TypeOf(ConnectionError, TimeoutError)
tracker = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
```

**조합 가능**: `&`, `|`, `~` 연산자로 tracker 조합 가능.

### [Trippers](trippers.md) {#trippers}

메트릭을 기반으로 circuit을 열고 닫을 시점을 결정합니다.

- **Closed/HalfOpened** - 상태 기반 조건
- **MinRequests** - 최소 호출 수
- **FailureRate** - 실패율
- **AvgLatency** - 평균 응답 시간
- **SlowRate** - 느린 호출 비율

```python
from fluxgate.trippers import Closed, MinRequests, FailureRate

tripper = Closed() & MinRequests(10) & FailureRate(0.5)
```

**조합 가능**: `&`, `|` 연산자로 조건 조합 가능.

### [Retries](retries.md) {#retries}

OPEN에서 HALF_OPEN 상태로 전환할 시점을 제어합니다.

- **Never** - 수동 리셋 필요
- **Always** - 즉시 재시도
- **Cooldown** - 고정 대기 시간
- **Backoff** - 지수 백오프

```python
from fluxgate.retries import Cooldown, Backoff

retry = Cooldown(duration=60.0, jitter_ratio=0.1)
retry = Backoff(initial=10.0, multiplier=2.0, max_duration=300.0)
```

### [Permits](permits.md) {#permits}

HALF_OPEN 상태에서 허용할 호출을 제어합니다.

- **Random** - 확률적 허용
- **RampUp** - 점진적 트래픽 증가

```python
from fluxgate.permits import Random, RampUp

permit = Random(ratio=0.5)
permit = RampUp(initial=0.1, final=0.8, duration=60.0)
```

### [Listeners](listeners/index.md) {#listeners}

상태 전환을 감지하고 외부 시스템에 알립니다.

- **LogListener** - 표준 로깅
- **PrometheusListener** - Prometheus 메트릭 (opt)
- **SlackListener** - Slack 알림 (opt)

```python
from fluxgate.listeners.log import LogListener

listeners = [LogListener()]
cb = CircuitBreaker(..., listeners=listeners)
```

## 전체 예제 {#full-example}

모든 것을 함께 사용:

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow
from fluxgate.trackers import Custom
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    tracker=Custom(is_server_error),
    tripper=MinRequests(20) & (
        (Closed() & FailureRate(0.6)) |
        (HalfOpened() & FailureRate(0.5))
    ),
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0),
    permit=RampUp(initial=0.1, final=0.5, duration=60.0),
)
```

## 다음 단계 {#next-steps}

각 컴포넌트를 자세히 살펴보세요:

- [Windows](windows.md) - 올바른 윈도우 타입 선택
- [Trackers](trackers.md) - 실패 기준 정의
- [Trippers](trippers.md) - Circuit 동작 설정
- [Retries](retries.md) - 복구 전략 계획
- [Permits](permits.md) - 복구 중 트래픽 제어
- [Listeners](listeners/index.md) - 상태 전환 모니터링
