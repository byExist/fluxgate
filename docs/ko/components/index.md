# 컴포넌트 개요

Fluxgate의 동작은 플러그인 가능한 컴포넌트 세트로 정의됩니다. 이 컴포넌트들을 조합함으로써 시스템의 필요에 정확히 맞는 회로 차단기를 구성할 수 있습니다. 각 컴포넌트는 로직의 특정 부분을 담당합니다.

## 아키텍처

| 컴포넌트 | 역할 | 조합 가능 여부 |
|---|---|---|
| **Window** | 최근 호출 결과를 저장하는 슬라이딩 윈도우. | 아니요 |
| **Tracker** | 어떤 결과(예: 특정 예외)가 실패로 간주되어야 하는지 식별합니다. | 예 (&, \|, ~) |
| **Tripper** | Window의 Metric을 사용하여 언제 회로를 트립할지 결정합니다. | 예 (&, \|) |
| **Retry** | `OPEN` 상태에서 `HALF_OPEN` 상태로 이동하는 조건을 정의합니다. | 아니요 |
| **Permit** | `HALF_OPEN` 상태에서 허용되는 "프로브" 호출 수를 관리합니다. | 아니요 |
| **Listener** | 상태 변경에 반응하여 로깅 또는 알림과 같은 부작용을 트리거합니다. | 아니요 |

---

## 컴포넌트 유형

### [Windows](windows.md)

Windows는 최근 호출 결과(성공, 실패, 응답 시간 등)를 저장하고, `tripper`가 회로를 열지 여부를 결정하는 데 사용하는 Metric을 제공합니다.

- **CountWindow**: 마지막 N개의 호출을 저장합니다.
- **TimeWindow**: 마지막 N초 동안의 호출을 저장합니다.

```python
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # 마지막 100개 호출 추적
window = TimeWindow(size=60)    # 마지막 60초 추적
```

### [Trackers](trackers.md)

Trackers는 호출 결과(예: 예외)를 검사하여 실패로 표시되어야 하는지 여부를 결정합니다.

- **All**: 모든 예외를 실패로 추적합니다.
- **TypeOf**: 특정 예외 유형만 추적합니다.
- **Custom**: 사용자 정의 함수로 실패 기준을 정의할 수 있습니다.

```python
from fluxgate.trackers import TypeOf, Custom

tracker = TypeOf(ConnectionError, TimeoutError)
tracker = Custom(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500)
```

**조합 가능**: `&` (AND), `|` (OR), `~` (NOT) 연산자를 사용하여 조합할 수 있습니다.

### [Trippers](trippers.md)

Trippers는 `CLOSED` 상태에서 `OPEN` 상태로 회로를 트립시키거나 다시 닫는 핵심 로직을 정의합니다. Window의 Metric을 분석하여 결정을 내립니다.

- **Closed/HalfOpened**: 특정 상태에서만 적용되는 조건을 생성합니다.
- **MinRequests**: 최소 호출 수가 충족되기 전에 브레이커가 트립되는 것을 방지합니다.
- **FailureRate**: 실패율이 특정 비율을 초과하면 트립됩니다.
- **AvgLatency**: 평균 응답 시간이 너무 높으면 트립됩니다.
- **SlowRate**: 느린 호출의 비율이 임계값을 초과하면 트립됩니다.

```python
from fluxgate.trippers import Closed, MinRequests, FailureRate

# CLOSED 상태에서 최소 10개의 요청과 50%의 실패율이 충족되면 트립됩니다.
tripper = Closed() & MinRequests(10) & FailureRate(0.5)
```

**조합 가능**: `&` (AND) 및 `|` (OR) 연산자를 사용하여 정교한 트립 조건을 구축합니다.

### [Retries](retries.md)

Retry는 쿨다운 기간을 제어하여 회로가 `OPEN` 상태에서 `HALF_OPEN` 상태로 이동하여 복구를 시도해야 하는 시점을 결정합니다.

- **Never**: 수동 재설정이 필요하며, 회로가 자동으로 복구되지 않습니다.
- **Always**: 즉시 복구를 시도합니다.
- **Cooldown**: 고정된 대기 시간 동안 기다린 후 전환합니다.
- **Backoff**: 반복적인 실패 후 대기 시간을 늘리는 지수 백오프 알고리즘을 사용합니다.

```python
from fluxgate.retries import Cooldown, Backoff

retry = Cooldown(duration=60.0, jitter_ratio=0.1)
retry = Backoff(initial=10.0, multiplier=2.0, max_duration=300.0)
```

### [Permits](permits.md)

Permit은 `HALF_OPEN` 상태에서 허용되는 호출 수를 관리하여 서비스 복구를 안전하게 테스트할 수 있도록 돕습니다.

- **All**: 모든 호출을 허용합니다 (테스트용).
- **Random**: 확률적으로 일정 비율의 호출을 통과시킵니다.
- **RampUp**: 설정된 기간 동안 허용되는 호출 비율을 점진적으로 증가시킵니다.

```python
from fluxgate.permits import All, Random, RampUp

permit = All()
permit = Random(ratio=0.5)
permit = RampUp(initial=0.1, final=0.8, duration=60.0)
```

### [Listeners](listeners/index.md)

Listeners는 상태 변경 이벤트에 등록하여 로깅, 모니터링 또는 알림과 같은 부작용을 트리거할 수 있습니다.

- **LogListener**: 표준 로깅에 상태 변경을 기록합니다.
- **PrometheusListener**: Prometheus 스크래핑을 위한 메트릭을 노출합니다. (optional)
- **SlackListener**: Slack 채널로 상태 변경 알림을 보냅니다. (optional)

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.log import LogListener

listeners = [LogListener()]
cb = CircuitBreaker(..., listeners=listeners)
```

## 전체 예제

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import TimeWindow
from fluxgate.trackers import TypeOf
from fluxgate.trippers import MinRequests, FailureRate, SlowRate
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    window=TimeWindow(size=60),  # 최근 60초 동안의 호출 추적
    tracker=TypeOf(ConnectionError, TimeoutError),
    tripper=MinRequests(10) & (FailureRate(0.5) | SlowRate(0.8)),
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0),
    permit=RampUp(initial=0.1, final=0.5, duration=60.0),
    slow_threshold=2.0,  # 2초 이상 걸리면 느린 호출로 간주
)
```

## 다음 단계

- [Windows](windows.md): 사용 사례에 맞는 올바른 Window 유형을 선택하는 방법을 배우세요.
- [Trackers](trackers.md): 정확한 실패 기준을 정의하세요.
- [Trippers](trippers.md): 회로를 트립시키는 강력한 조건을 구축하세요.
- [Retries](retries.md): 복구 조건을 설계하세요.
- [Permits](permits.md): 복구 기간 동안 트래픽을 안전하게 관리하세요.
- [Listeners](listeners/index.md): 모니터링 및 알림 스택과 통합하세요.
