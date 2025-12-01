# PrometheusListener

Prometheus 메트릭을 수집하여 Circuit Breaker의 상태를 모니터링하는 리스너입니다.

## 설치 {#installation}

```bash
pip install fluxgate[prometheus]
```

## 메트릭 {#metrics}

### circuit_breaker_state (Gauge)

현재 Circuit Breaker의 상태를 나타냅니다.

**Labels:**

- `circuit_name`: Circuit Breaker 이름
- `state`: 상태값 (`closed`, `open`, `half_open`, `metrics_only`, `disabled`, `forced_open`)

**값:** `1` (현재 상태) / `0` (현재 상태 아님)

### circuit_breaker_state_transition (Counter)

상태 전환 횟수를 카운팅합니다.

**Labels:**

- `circuit_name`: Circuit Breaker 이름
- `old_state`: 이전 상태
- `new_state`: 새 상태

## 사용법 {#usage}

### 동기 Circuit Breaker

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Prometheus 메트릭 서버 시작
start_http_server(8000)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[PrometheusListener()],
)

# 메트릭: http://localhost:8000/metrics
```

### 비동기 Circuit Breaker

```python
from prometheus_client import start_http_server
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Prometheus 메트릭 서버 시작 (별도 스레드)
start_http_server(8000)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[PrometheusListener()],
)
```

### FastAPI 통합

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

app = FastAPI()

# Prometheus 메트릭 엔드포인트 마운트
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

cb = AsyncCircuitBreaker(
    name="api_gateway",
    ...,
    listeners=[PrometheusListener()],
)
```

> **참고**: `prometheus_client`는 thread-safe하며 동기/비동기 코드 모두에서 사용 가능합니다.
> 자세한 내용은 [공식 문서](https://prometheus.github.io/client_python/)를 참고하세요.

## 여러 Circuit Breaker 모니터링 {#multiple-circuits}

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

start_http_server(8000)

# 리스너 인스턴스 재사용
listener = PrometheusListener()

payment_cb = CircuitBreaker(name="payment_api", ..., listeners=[listener])
inventory_cb = CircuitBreaker(name="inventory_api", ..., listeners=[listener])
```

## 커스텀 메트릭 {#custom-metrics}

추가 메트릭이 필요한 경우 `IListener`를 구현하여 커스텀 리스너를 작성하세요:

```python
from prometheus_client import Counter
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

CUSTOM_METRIC = Counter('my_custom_metric', 'Description', ['circuit_name'])

class CustomListener(IListener):
    def __call__(self, signal: Signal) -> None:
        # 커스텀 로직
        CUSTOM_METRIC.labels(circuit_name=signal.circuit_name).inc()
```

## 다음 단계 {#next-steps}

- [SlackListener](slack.md) - 실시간 알림 설정
- [LogListener](logging.md) - 로깅 설정
- [Overview](index.md) - 리스너 개요로 돌아가기
