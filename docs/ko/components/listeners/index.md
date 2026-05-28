# Listener

Listener는 Circuit Breaker 상태 전환을 감지하고 외부 시스템에 알림을 보냅니다. 각 Listener는 자기 `name`을 가지며 — 메트릭 라벨, 로그 메시지, 알림의 식별자로 사용됩니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(
    ...,
    listeners=[
        LogListener(name="payment_api"),
        PrometheusListener(name="payment_api"),
    ],
)
```

## Signal {#signal}

Listener는 상태 전환 시 `Signal` 객체를 받습니다.

```python
from dataclasses import dataclass
from fluxgate.state import StateEnum

@dataclass(frozen=True)
class Signal:
    old_state: StateEnum  # 이전 상태
    new_state: StateEnum  # 새 상태
    timestamp: float      # 전환 시간 (Unix 타임스탬프)
```

## 동기 vs 비동기 {#sync-vs-async}

### 동기 Listener (Listener)

`CircuitBreaker` 및 `AsyncCircuitBreaker` 모두에서 사용할 수 있습니다.

```python
from fluxgate.listeners import Listener
from fluxgate.signal import Signal

class CustomListener(Listener):
    def __init__(self, name: str) -> None:
        self._name = name

    def __call__(self, signal: Signal) -> None:
        print(f"{self._name}: {signal.old_state} → {signal.new_state}")
```

!!! warning "주의"
    `AsyncCircuitBreaker`와 함께 동기 Listener를 사용할 때, 이벤트 루프를 차단하는 블로킹 I/O 작업(네트워크 호출 등)을 피하십시오. I/O가 필요한 작업에는 `AsyncListener`를 사용하십시오.

### 비동기 Listener (AsyncListener)

`AsyncCircuitBreaker`에서만 사용할 수 있습니다.

```python
from fluxgate.listeners import AsyncListener
from fluxgate.signal import Signal

class CustomAsyncListener(AsyncListener):
    async def __call__(self, signal: Signal) -> None:
        await send_notification(signal)
```

## 사용 가능한 Listener {#available-listeners}

### [LogListener](logging.md)

Python의 표준 `logging` 모듈을 사용하여 Circuit Breaker 상태 전환을 로깅합니다.

```python
from fluxgate.listeners.log import LogListener

cb = CircuitBreaker(..., listeners=[LogListener(name="payment_api")])
```

### [PrometheusListener](prometheus.md)

모니터링 시스템과의 통합을 위해 Prometheus Metric을 수집합니다.

```bash
pip install fluxgate[prometheus]
```

```python
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(..., listeners=[PrometheusListener(name="payment_api")])
```

### [SlackListener / AsyncSlackListener](slack.md)

Circuit Breaker 상태 전환 알림을 Slack 채널로 보냅니다.

```bash
pip install fluxgate[slack]
```

```python
from fluxgate.listeners.slack import SlackListener, AsyncSlackListener

# 동기
sync_cb = CircuitBreaker(..., listeners=[
    SlackListener(name="payment_api", channel="C1234567890", token="xoxb-...")
])

# 비동기
async_cb = AsyncCircuitBreaker(..., listeners=[
    AsyncSlackListener(name="payment_api", channel="C1234567890", token="xoxb-...")
])
```

## 커스텀 Listener {#custom-listeners}

### 동기 Listener

```python
from fluxgate.listeners import Listener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

class DatabaseListener(Listener):
    def __init__(self, name: str, db_connection):
        self._name = name
        self.db = db_connection

    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            self.db.execute(
                "INSERT INTO circuit_events (name, timestamp) VALUES (?, ?)",
                (self._name, signal.timestamp)
            )
```

### 비동기 Listener

```python
import httpx
from fluxgate.listeners import AsyncListener
from fluxgate.signal import Signal

class WebhookListener(AsyncListener):
    def __init__(self, name: str, webhook_url: str):
        self._name = name
        self.url = webhook_url
        self.client = httpx.AsyncClient()

    async def __call__(self, signal: Signal) -> None:
        payload = {
            "circuit": self._name,
            "transition": f"{signal.old_state.value} -> {signal.new_state.value}",
            "timestamp": signal.timestamp,
        }
        await self.client.post(self.url, json=payload)
```

## 오류 처리 {#error-handling}

Listener에서 발생하는 예외는 Circuit Breaker 동작에 영향을 미치지 않습니다. 예외는 로깅되며 Circuit Breaker는 정상적으로 계속 작동합니다.

## 여러 Listener 조합 {#combining-listeners}

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener
from fluxgate.listeners.slack import SlackListener

cb = CircuitBreaker(
    ...,
    listeners=[
        LogListener(name="payment_api"),
        PrometheusListener(name="payment_api"),
        SlackListener(name="payment_api", channel="C1234567890", token="xoxb-..."),
    ],
)
```

## 다음 단계 {#next-steps}

- [LogListener](logging.md) - 로깅 구성
- [PrometheusListener](prometheus.md) - Prometheus 통합
- [SlackListener](slack.md) - Slack 알림 설정
- [개요](index.md) - Listener 개요로 돌아가기
