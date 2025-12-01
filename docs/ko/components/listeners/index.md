# Listeners

Listener는 Circuit Breaker의 상태 전환을 감지하고 외부 시스템에 알림을 보냅니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(
    name="api",
    ...,
    listeners=[
        LogListener(),
        PrometheusListener(),
    ],
)
```

## Signal {#signal}

리스너는 상태 전환 시 `Signal` 객체를 받습니다:

```python
@dataclass(frozen=True)
class Signal:
    circuit_name: str     # Circuit Breaker 이름
    old_state: StateEnum  # 이전 상태
    new_state: StateEnum  # 새로운 상태
    timestamp: float      # 전환 시각 (Unix timestamp)
```

## 동기 vs 비동기 {#sync-vs-async}

### 동기 리스너 (IListener)

`CircuitBreaker`와 `AsyncCircuitBreaker` 모두에서 사용 가능:

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

class CustomListener(IListener):
    def __call__(self, signal: Signal) -> None:
        print(f"{signal.circuit_name}: {signal.old_state} → {signal.new_state}")
```

> **주의**: `AsyncCircuitBreaker`에서 동기 리스너 사용 시, 블로킹 I/O 작업(네트워크 호출, 파일 쓰기 등)이 있다면 이벤트 루프를 막을 수 있습니다. 블로킹 작업이 필요한 경우 `IAsyncListener`를 사용하세요.

### 비동기 리스너 (IAsyncListener)

`AsyncCircuitBreaker`에서만 사용 가능:

```python
from fluxgate.interfaces import IAsyncListener
from fluxgate.signal import Signal

class CustomAsyncListener(IAsyncListener):
    async def __call__(self, signal: Signal) -> None:
        await send_notification(signal)
```

## 사용 가능한 리스너 {#available-listeners}

### [LogListener](logging.md)

표준 라이브러리의 `logging` 모듈을 사용하여 상태 전환을 로깅합니다.

```python
from fluxgate.listeners.log import LogListener

cb = CircuitBreaker(..., listeners=[LogListener()])
```

### [PrometheusListener](prometheus.md)

Prometheus 메트릭을 수집하여 모니터링 시스템과 연동합니다.

```bash
pip install fluxgate[prometheus]
```

```python
from fluxgate.listeners.prometheus import PrometheusListener

cb = CircuitBreaker(..., listeners=[PrometheusListener()])
```

### [SlackListener / AsyncSlackListener](slack.md)

Slack 채널에 상태 전환 알림을 전송합니다.

```bash
pip install fluxgate[slack]
```

```python
from fluxgate.listeners.slack import SlackListener, AsyncSlackListener

# 동기
sync_cb = CircuitBreaker(..., listeners=[
    SlackListener(channel="C1234567890", token="xoxb-...")
])

# 비동기
async_cb = AsyncCircuitBreaker(..., listeners=[
    AsyncSlackListener(channel="C1234567890", token="xoxb-...")
])
```

## 커스텀 리스너 {#custom-listeners}

### 동기 리스너

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

class DatabaseListener(IListener):
    def __init__(self, db_connection):
        self.db = db_connection

    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            self.db.execute(
                "INSERT INTO circuit_events (name, timestamp) VALUES (?, ?)",
                (signal.circuit_name, signal.timestamp)
            )
```

### 비동기 리스너

```python
import httpx
from fluxgate.interfaces import IAsyncListener
from fluxgate.signal import Signal

class WebhookListener(IAsyncListener):
    def __init__(self, webhook_url: str):
        self.url = webhook_url
        self.client = httpx.AsyncClient()

    async def __call__(self, signal: Signal) -> None:
        payload = {
            "circuit": signal.circuit_name,
            "transition": f"{signal.old_state.value} → {signal.new_state.value}",
            "timestamp": signal.timestamp,
        }
        await self.client.post(self.url, json=payload)
```

## 에러 처리 {#error-handling}

리스너에서 예외가 발생해도 Circuit Breaker의 동작에는 영향을 주지 않습니다. 예외는 자동으로 로깅되며, Circuit Breaker는 정상적으로 동작을 계속합니다.

## 여러 리스너 조합 {#combining-listeners}

```python
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.listeners.prometheus import PrometheusListener
from fluxgate.listeners.slack import SlackListener

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[
        LogListener(),
        PrometheusListener(),
        SlackListener(channel="C1234567890", token="xoxb-..."),
    ],
)
```

## 다음 단계 {#next-steps}

- [LogListener](logging.md) - 로깅 설정
- [PrometheusListener](prometheus.md) - Prometheus 연동
- [SlackListener](slack.md) - Slack 알림 설정
