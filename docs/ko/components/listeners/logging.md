# LogListener

`LogListener`는 Circuit Breaker의 동작을 관찰하는 가장 간단한 방법을 제공합니다. Python의 표준 `logging` 모듈에 연결하여 상태 전환을 기록하며, 서킷 브레이커가 어떻게 작동하는지에 대한 명확하고 시간순으로 된 보기를 제공합니다.

`CircuitBreaker` 및 `AsyncCircuitBreaker` 에서 활용할 수 있습니다.

## 기본 사용법 {#usage}

`LogListener`를 Circuit Breaker의 `listeners` 목록에 추가합니다.

<!--pytest.mark.skip-->

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

# 콘솔 로깅을 위한 기본 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener()],
)
```

Circuit Breaker가 상태를 변경하면 다음과 같은 로그 레코드를 생성합니다.

```text
[2025-01-15 10:30:45] Circuit Breaker 'payment_api' transitioned from CLOSED to OPEN
[2025-01-15 10:31:45] Circuit Breaker 'payment_api' transitioned from OPEN to HALF_OPEN
[2025-01-15 10:31:50] Circuit Breaker 'payment_api' transitioned from HALF_OPEN to CLOSED
```

---

## 커스텀 Logger {#custom-logger}

기본적으로 `LogListener`는 루트 logger를 사용합니다. 로그 라우팅과 포맷팅을 더 세밀하게 제어하려면 직접 logger를 주입할 수 있습니다.

<!--pytest.mark.skip-->

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

# Circuit Breaker 이벤트 전용 logger 생성
cb_logger = logging.getLogger("myapp.circuit_breaker")
cb_logger.setLevel(logging.INFO)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener(logger=cb_logger)],
)
```

---

## 커스텀 로그 레벨 {#custom-log-levels}

`level_map`을 사용하여 각 상태 전환에 대한 로그 레벨을 커스터마이징할 수 있습니다. 기본적으로 `OPEN`과 `FORCED_OPEN`으로의 전환은 `WARNING` 레벨로, 나머지는 `INFO` 레벨로 기록됩니다.

<!--pytest.mark.skip-->

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener
from fluxgate.state import StateEnum

# OPEN 전환을 ERROR로 기록하여 알림 트리거
level_map = {
    StateEnum.OPEN: logging.ERROR,
    StateEnum.HALF_OPEN: logging.WARNING,
    StateEnum.CLOSED: logging.DEBUG,
}

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener(level_map=level_map)],
)
```

두 옵션을 함께 사용할 수도 있습니다:

<!--pytest.mark.skip-->

```python
cb_logger = logging.getLogger("myapp.circuit_breaker")
listener = LogListener(logger=cb_logger, level_map=level_map)
```

---

## 구조화된 (JSON) 로깅 구현 {#structured-logging}

최신 플랫폼에서 더 나은 가시성을 위해 JSON과 같은 구조화된 형식으로 로그를 출력하는 사용자 정의 Listener를 만들 수 있습니다.

```python
import json
import logging
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

class JsonLogListener(IListener):
    def __init__(self, logger):
        self.logger = logger

    def __call__(self, signal: Signal) -> None:
        log_data = {
            "message": "Circuit breaker transition",
            "circuit_name": signal.circuit_name,
            "previous_state": signal.old_state.value,
            "current_state": signal.new_state.value,
            "timestamp_utc": signal.timestamp,
        }
        self.logger.info(json.dumps(log_data))

# 사용
json_logger = logging.getLogger("json_logger")
cb_listener = JsonLogListener(json_logger)
```

## 파일 로깅 구성 {#file-logging}

Circuit Breaker 로그를 파일로 보내려면 애플리케이션의 로깅 설정에서 적절한 핸들러를 구성합니다. `LogListener`는 이 구성을 자동으로 사용합니다.

<!--pytest.mark.skip-->

```python
import logging
from logging.handlers import RotatingFileHandler
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

# 로테이팅 파일 핸들러 구성
handler = RotatingFileHandler(
    filename='circuit_breaker.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# 루트 로거에 핸들러 추가
root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

# LogListener는 이제 루트 로거를 통해 파일에 기록합니다.
log_listener = LogListener()
```

## 다음 단계 {#next-steps}

- [PrometheusListener](prometheus.md): 시계열 모니터링을 위한 메트릭 노출.
- [SlackListener](slack.md): 상태 변경에 대한 실시간 알림 전송.
- [Listener 개요](index.md): 메인 Listener 페이지로 돌아갑니다.
