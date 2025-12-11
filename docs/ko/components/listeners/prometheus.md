# PrometheusListener

`PrometheusListener`는 Circuit Breaker의 상태와 전환을 Prometheus 서버에서 스크랩할 수 있는 메트릭으로 내보냅니다. 이를 통해 대시보드를 구축하고, 알림을 생성하며, 시간이 지남에 따라 서비스의 안정성에 대한 깊은 통찰력을 얻을 수 있습니다.

## 설치 {#installation}

이 Listener는 `prometheus-client` 라이브러리가 필요합니다. 다음 명령어로 추가 설치할 수 있습니다.

```bash
pip install fluxgate[prometheus]
```

---

## 노출되는 메트릭 {#metrics}

두 가지 핵심 메트릭을 내보냅니다.

### `circuit_breaker_state` (Gauge)

이 메트릭은 Circuit Breaker의 **현재 상태**를 나타냅니다. Gauge이므로 값이 오르거나 내릴 수 있습니다.

**라벨:**

- `circuit_name`: Circuit Breaker의 이름.
- `state`: 상태의 이름 (`closed`, `open`, `half_open` 등).

**값:**

- `1`: Circuit이 현재 이 상태에 있습니다.
- `0`: Circuit이 이 상태에 있지 않습니다.

**PromQL 사용 예시:**

- **모든 열린 Circuit 찾기:**

    ```promql
    circuit_breaker_state{state="open"} == 1
    ```

- **각 상태에 있는 Circuit의 수 계산:**

    ```promql
    sum(circuit_breaker_state) by (state)
    ```

### `circuit_breaker_state_transition_total` (Counter)

이 메트릭은 Circuit Breaker가 한 상태에서 다른 상태로 전환된 총 횟수를 **계산**합니다. Counter이므로 값은 항상 증가하기만 합니다.

**라벨:**

- `circuit_name`: Circuit Breaker의 이름.
- `old_state`: Circuit이 전환된 **이전** 상태.
- `new_state`: Circuit이 전환된 **새로운** 상태.

**PromQL 사용 예시:**

- **지난 5분 동안 Circuit이 열린 비율 계산:**

    ```promql
    sum(rate(circuit_breaker_state_transition_total{new_state="open"}[5m])) by (circuit_name)
    ```

- **지난 1시간 동안 `HALF_OPEN` 상태로의 모든 전환 횟수 계산:**

    ```promql
    increase(circuit_breaker_state_transition_total{new_state="half_open"}[1h])
    ```

---

## 사용법 {#usage}

### 기본 설정

간단한 스크립트나 백그라운드 워커의 경우, Prometheus 클라이언트의 HTTP 서버를 별도의 스레드에서 시작할 수 있습니다.

<!--pytest.mark.skip-->

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# 포트 8000에서 Prometheus 메트릭 서버를 시작합니다.
# 이 서버는 백그라운드 스레드에서 실행되며 블로킹되지 않습니다.
start_http_server(8000)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[PrometheusListener()],
)

# 여기에 애플리케이션 로직을 작성...
# 메트릭은 http://localhost:8000/metrics 에서 확인 가능합니다.
```

### 웹 프레임워크와의 통합 (FastAPI)

FastAPI 또는 Flask와 같은 웹 프레임워크를 사용할 때는 별도의 서버를 시작하는 대신 Prometheus 메트릭 엔드포인트를 애플리케이션에 직접 통합해야 합니다.

<!--pytest.mark.skip-->

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

# Prometheus 메트릭을 위한 ASGI 앱을 생성합니다.
metrics_app = make_asgi_app()

app = FastAPI()
# /metrics 엔드포인트에 메트릭 앱을 마운트합니다.
app.mount("/metrics", metrics_app)

cb = AsyncCircuitBreaker(
    name="api_gateway",
    ...,
    listeners=[PrometheusListener()],
)

@app.get("/")
@cb
async def root():
    # 보호된 API 로직...
    return {"message": "Hello World"}
```

> **참고**: `prometheus-client` 라이브러리는 스레드 안전하므로, 단일 `PrometheusListener` 인스턴스를 동기 및 비동기 Circuit Breaker 모두에서 안전하게 사용할 수 있습니다. 자세한 내용은 [공식 문서](https://prometheus.io/client/python/docs/)를 참조하십시오.

---

## 여러 Circuit Breaker 모니터링 {#multiple-circuits}

동일한 애플리케이션에서 여러 Circuit Breaker를 모니터링하려면, 동일한 `PrometheusListener` 인스턴스를 재사용하기만 하면 됩니다. 각 브레이커에 대해 메트릭은 `circuit_name`으로 올바르게 라벨링됩니다.

<!--pytest.mark.skip-->

```python
from prometheus_client import start_http_server
from fluxgate import CircuitBreaker
from fluxgate.listeners.prometheus import PrometheusListener

start_http_server(8000)

# 단일 Listener 인스턴스를 생성합니다.
listener = PrometheusListener()

# 여러 브레이커에 동일한 인스턴스를 추가합니다.
payment_cb = CircuitBreaker(name="payment_api", ..., listeners=[listener])
inventory_cb = CircuitBreaker(name="inventory_api", ..., listeners=[listener])
```

---

## Grafana 대시보드 예시

다음은 Grafana 대시보드에서 이러한 메트릭을 시각화하는 방법의 몇 가지 예시입니다.

### 패널: "현재 열린 Circuit" (Stat)

- **쿼리**: `sum(circuit_breaker_state{state="open"})`
- **시각화**: Stat
- **단위**: 없음
- **임계값**: 기본: 0, 단계 1: 1 (경고), 단계 2: 5 (치명적)
- **설명**: 현재 `OPEN` 상태에 있는 모든 Circuit Breaker의 실시간 수를 보여줍니다.

### 패널: "Circuit 트립률 (5분)" (Time Series)

- **쿼리**: `sum(rate(circuit_breaker_state_transition_total{new_state="open"}[5m])) by (circuit_name)`
- **시각화**: 시계열
- **단위**: 초당 전환 수
- **범례**: `{{circuit_name}}`
- **설명**: 지난 5분 동안 평균화된, Circuit이 열린 초당 트립률을 보여줍니다. 추세를 파악하고 문제 있는 서비스를 식별하는 데 유용합니다.

### 패널: "Circuit 상태 개요" (Pie Chart)

- **쿼리**: `sum(circuit_breaker_state) by (state)`
- **시각화**: 파이 차트
- **단위**: 없음
- **값 옵션**: `모든 값`
- **설명**: 전체 시스템에 걸쳐 Circuit Breaker 상태 분포에 대한 높은 수준의 개요를 제공합니다.

---

## 커스텀 메트릭 {#custom-metrics}

추가적인 커스텀 메트릭을 내보내야 하는 경우, `IListener` 인터페이스를 구현하여 자체 Listener를 만들 수 있습니다.

```python
from prometheus_client import Counter
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

# OPEN 전환만 계산하는 커스텀 메트릭을 정의합니다.
OPEN_TRANSITIONS = Counter(
    'circuit_breaker_open_total',
    'Circuit Breaker가 열린 총 횟수',
    ['circuit_name']
)

class CustomPrometheusListener(IListener):
    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            OPEN_TRANSITIONS.labels(circuit_name=signal.circuit_name).inc()
```

## 다음 단계 {#next-steps}

- [SlackListener](slack.md): 상태 변경에 대한 실시간 알림을 받습니다.
- [LogListener](logging.md): 전환에 대한 상세 로깅을 구성합니다.
- [Listener 개요](index.md): 메인 Listener 페이지로 돌아갑니다.
