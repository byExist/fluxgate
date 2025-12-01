# LogListener

Python 표준 라이브러리의 `logging` 모듈을 사용하여 Circuit Breaker의 상태 전환을 로깅하는 리스너입니다.

## 사용법 {#usage}

### 동기 Circuit Breaker

```python
import logging
from fluxgate import CircuitBreaker
from fluxgate.listeners.log import LogListener

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[LogListener()],
)
```

**출력 예시:**

```txt
[2025-01-15 10:30:45] Circuit Breaker 'payment_api' transitioned from CLOSED to OPEN
[2025-01-15 10:31:45] Circuit Breaker 'payment_api' transitioned from OPEN to HALF_OPEN
[2025-01-15 10:31:50] Circuit Breaker 'payment_api' transitioned from HALF_OPEN to CLOSED
```

### 비동기 Circuit Breaker

```python
import logging
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.log import LogListener

logging.basicConfig(level=logging.INFO)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[LogListener()],
)
```

## 커스텀 로그 레벨 {#custom-log-level}

다른 로그 레벨을 사용하려면 커스텀 리스너를 작성하세요:

```python
import logging
import time
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum

class WarningLogListener(IListener):
    """OPEN 상태 전환만 WARNING 레벨로 로깅"""

    def __call__(self, signal: Signal) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(signal.timestamp))
        message = (
            f"[{timestamp}] Circuit Breaker '{signal.circuit_name}' "
            f"transitioned from {signal.old_state.value} to {signal.new_state.value}"
        )

        if signal.new_state == StateEnum.OPEN:
            logging.warning(message)
        else:
            logging.info(message)
```

## 구조화된 로깅 {#structured-logging}

JSON 형태로 로깅:

```python
import json
import logging
import time
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal

class JsonLogListener(IListener):
    def __call__(self, signal: Signal) -> None:
        log_data = {
            "event": "circuit_breaker_transition",
            "circuit_name": signal.circuit_name,
            "old_state": signal.old_state.value,
            "new_state": signal.new_state.value,
            "timestamp": signal.timestamp,
        }
        logging.info(json.dumps(log_data))
```

## 파일 로깅 {#file-logging}

```python
import logging
from logging.handlers import RotatingFileHandler
from fluxgate.listeners.log import LogListener

handler = RotatingFileHandler(
    'circuit_breaker.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

cb = CircuitBreaker(..., listeners=[LogListener()])
```

## 다음 단계 {#next-steps}

- [PrometheusListener](prometheus.md) - 메트릭 기반 모니터링
- [SlackListener](slack.md) - 실시간 알림
- [Overview](index.md) - 리스너 개요로 돌아가기
