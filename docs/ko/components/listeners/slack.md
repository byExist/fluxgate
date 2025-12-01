# SlackListener / AsyncSlackListener

Slack 채널에 Circuit Breaker 상태 전환 알림을 전송하는 리스너입니다.

## 설치 {#installation}

```bash
pip install fluxgate[slack]
```

## Slack 설정 {#slack-setup}

### 1. Slack App 생성

1. [https://api.slack.com/apps](https://api.slack.com/apps)에서 "Create New App"
2. "From scratch" 선택
3. App 이름 및 Workspace 선택

### 2. Bot Token 권한

**OAuth & Permissions**에서 다음 권한 추가:

- `chat:write` - 메시지 전송
- `chat:write.public` - 공개 채널에 메시지 전송 (선택)

### 3. Bot Token 복사

**OAuth & Permissions** → **Bot User OAuth Token** (xoxb-로 시작)

### 4. 채널 ID 확인

채널 우클릭 → "View channel details" → Channel ID 복사 (예: C1234567890)

## 사용법 {#usage}

### 동기 Circuit Breaker

```python
import os
from fluxgate import CircuitBreaker
from fluxgate.listeners.slack import SlackListener

slack = SlackListener(
    channel=os.environ["SLACK_CHANNEL"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[slack],
)
```

### 비동기 Circuit Breaker

```python
import os
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.slack import AsyncSlackListener

slack = AsyncSlackListener(
    channel=os.environ["SLACK_CHANNEL"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[slack],
)
```

## 메시지 형식 {#message-format}

### CLOSED → OPEN

- 🚨 Circuit Breaker Triggered
- 빨강색 (#FF4C4C)
- 새 스레드 시작

### OPEN → HALF_OPEN

- 🔄 Attempting Circuit Breaker Recovery
- 주황색 (#FFA500)
- 같은 스레드에 답글

### HALF_OPEN → OPEN

- ⚠️ Circuit Breaker Re-triggered
- 빨강색 (#FF4C4C)
- 같은 스레드에 답글

### HALF_OPEN → CLOSED

- ✅ Circuit Breaker Recovered
- 초록색 (#36a64f)
- 같은 스레드에 답글 + 채널 브로드캐스트

## 조건부 알림 {#conditional-notifications}

특정 상태 전환만 알림받기:

```python
from fluxgate.interfaces import IListener
from fluxgate.signal import Signal
from fluxgate.state import StateEnum
from fluxgate.listeners.slack import SlackListener

class CriticalSlackListener(IListener):
    """OPEN 상태 전환만 알림"""

    def __init__(self, channel: str, token: str):
        self._slack = SlackListener(channel, token)

    def __call__(self, signal: Signal) -> None:
        if signal.new_state == StateEnum.OPEN:
            self._slack(signal)
```

## 커스텀 메시지 {#custom-messages}

메시지 포맷을 커스터마이징하려면 `IListener`를 직접 구현하세요. Slack API 메시지 형식은 [공식 문서](https://api.slack.com/messaging/composing)를 참고하세요.

## 문제 해결 {#troubleshooting}

- **401 Unauthorized**: Bot Token 확인
- **403 Forbidden**: `chat:write` 권한 및 Workspace 설치 확인
- **404 Channel Not Found**: 채널 ID 확인 및 Bot 초대 여부 확인

## 다음 단계 {#next-steps}

- [PrometheusListener](prometheus.md) - 메트릭 기반 모니터링
- [LogListener](logging.md) - 로깅 설정
- [Overview](index.md) - 리스너 개요로 돌아가기
