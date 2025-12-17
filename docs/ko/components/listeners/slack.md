# SlackListener / AsyncSlackListener

`SlackListener`와 `AsyncSlackListener`는 Circuit Breaker 상태 변경에 대한 실시간 알림을 Slack 채널로 직접 푸시합니다. 이는 중요한 서비스가 실패하기 시작할 때 담당 엔지니어에게 즉시 알려, 더 빠른 대응을 가능하게 하는 데 매우 중요합니다.

## 설치 {#installation}

이 Listener는 HTTP 요청을 위해 `httpx`가 필요합니다. 다음 명령어로 추가 설치할 수 있습니다.

```bash
pip install fluxgate[slack]
```

---

## Slack 설정 {#slack-setup}

### 1. Slack 앱 생성

1. [https://api.slack.com/apps](https://api.slack.com/apps)으로 이동하여 **Create New App**을 클릭합니다.
2. **From scratch**를 선택하고, 앱 이름(예: "Circuit Breaker Alerts")을 입력한 다음, 작업 공간을 선택합니다.

### 2. 봇 토큰 범위 추가

사이드바에서 **OAuth & Permissions**로 이동하여 "Scopes" 섹션까지 아래로 스크롤합니다. 다음 **봇 토큰 범위**를 추가합니다.

- `chat:write`: 메시지를 보내기 위함.
- `chat:write.public`: 공개 채널에 메시지를 보내기 위함 (선택 사항).

### 3. 앱 설치 및 토큰 복사

1. **OAuth & Permissions** 페이지 상단으로 다시 스크롤하여 **Install to Workspace**를 클릭합니다.
2. 설치 후 **봇 사용자 OAuth 토큰**을 복사합니다. `xoxb-`로 시작합니다.

### 4. 채널 ID 가져오기 및 봇 초대

1. Slack 클라이언트에서 알림을 받을 채널을 마우스 오른쪽 버튼으로 클릭하고 "채널 세부 정보 보기"를 선택한 다음, 팝업 하단에서 **채널 ID**를 복사합니다(예: `C1234567890`).
2. 동일한 채널에서 `/invite @YourAppName`을 입력하여 봇을 채널에 추가하면 메시지를 게시할 권한을 갖게 됩니다.

---

## 사용법 {#usage}

Slack 토큰과 채널 ID를 소스 코드에 하드 코딩하는 대신 환경 변수로 저장하는 것을 강력히 권장합니다.

### 동기 (`SlackListener`)

표준 `CircuitBreaker`와 함께 `SlackListener`를 사용합니다.

<!--pytest.mark.skip-->

```python
import os
from fluxgate import CircuitBreaker
from fluxgate.listeners.slack import SlackListener

slack_listener = SlackListener(
    channel=os.environ["SLACK_CHANNEL_ID"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = CircuitBreaker(
    name="payment_api",
    ...,
    listeners=[slack_listener],
)
```

### 비동기 (`AsyncSlackListener`)

`AsyncCircuitBreaker`와 함께 `AsyncSlackListener`를 사용합니다. 기본 HTTP 호출은 비동기적으로 이루어집니다.

<!--pytest.mark.skip-->

```python
import os
from fluxgate import AsyncCircuitBreaker
from fluxgate.listeners.slack import AsyncSlackListener

slack_listener = AsyncSlackListener(
    channel=os.environ["SLACK_CHANNEL_ID"],
    token=os.environ["SLACK_BOT_TOKEN"]
)

cb = AsyncCircuitBreaker(
    name="async_api",
    ...,
    listeners=[slack_listener],
)
```

---

## 메시지 형식 {#message-format}

Listener는 장애 사이클을 기반으로 대화를 체계적으로 유지하기 위해 스레드 메시지를 보냅니다:

- **스레드 시작**: **→ OPEN** 전환 시 (새로운 또는 지속되는 장애 사이클)
- **스레드 종료**: **→ CLOSED**, **→ DISABLED**, 또는 **→ METRICS_ONLY** 전환 시

| 전환 | 제목 | 색상 | 설명 |
|---|---|---|---|
| CLOSED → OPEN | 🚨 Circuit Breaker Triggered | 빨간색 | 새 스레드 시작 |
| OPEN → HALF_OPEN | 🔄 Attempting Circuit Breaker Recovery | 주황색 | 스레드에 회신 |
| HALF_OPEN → OPEN | ⚠️ Circuit Breaker Re-triggered | 빨간색 | 스레드에 회신 (스레드 유지) |
| HALF_OPEN → CLOSED | ✅ Circuit Breaker Recovered | 녹색 | 회신 + 브로드캐스트 후 스레드 정리 |
| 기타 모든 전환 | ℹ️ Circuit Breaker State Changed | 회색 | 수동 전환용 fallback |

`CLOSED`, `DISABLED`, `METRICS_ONLY`로 전환 시 현재 스레드가 종료되어, 다음 장애 사이클은 새 스레드로 시작됩니다. `FORCED_OPEN`으로 전환 시에는 장애 사이클이 계속되므로 스레드가 유지됩니다.

---

## 고급 사용법

### 사용자 정의 메시지 {#custom-messages}

메시지 템플릿을 사용자 정의하려면(예: 다른 언어) `SlackListener`를 상속하고 클래스 속성을 오버라이드할 수 있습니다.

각 템플릿은 세 개의 필수 키를 가진 `Template` TypedDict입니다:

- `title`: 메시지 제목 (이모지 지원)
- `color`: 첨부 파일 사이드바의 Hex 색상 코드
- `description`: 상태 변경에 대한 상세 설명

<!--pytest.mark.skip-->

```python
from fluxgate.listeners.slack import SlackListener, Template
from fluxgate.state import StateEnum

class KoreanSlackListener(SlackListener):
    """한국어 메시지를 사용하는 SlackListener."""

    TRANSITION_TEMPLATES: dict[tuple[StateEnum, StateEnum], Template] = {
        (StateEnum.CLOSED, StateEnum.OPEN): {
            "title": "🚨 서킷 브레이커 작동",
            "color": "#FF4C4C",
            "description": "요청 실패율이 임계값을 초과했습니다.",
        },
        (StateEnum.OPEN, StateEnum.HALF_OPEN): {
            "title": "🔄 서킷 브레이커 복구 시도 중",
            "color": "#FFA500",
            "description": "부분 요청으로 서비스 상태를 테스트하고 있습니다.",
        },
        (StateEnum.HALF_OPEN, StateEnum.OPEN): {
            "title": "⚠️ 서킷 브레이커 재작동",
            "color": "#FF4C4C",
            "description": "테스트 요청이 실패하여 열림 상태로 복귀합니다.",
        },
        (StateEnum.HALF_OPEN, StateEnum.CLOSED): {
            "title": "✅ 서킷 브레이커 복구됨",
            "color": "#36a64f",
            "description": "테스트 요청이 성공하여 서비스가 정상입니다.",
        },
    }

    FALLBACK_TEMPLATE: Template = {
        "title": "ℹ️ 서킷 브레이커 상태 변경",
        "color": "#808080",
        "description": "서킷 브레이커 상태가 변경되었습니다.",
    }
```

---

## 문제 해결 {#troubleshooting}

- **`invalid_auth` 오류**: 봇 토큰이 잘못되었거나 해지되었을 가능성이 있습니다.
- **`not_in_channel` 오류**: 봇을 채널에 초대하지 않았습니다. 채널에서 `/invite @YourAppName`을 입력하십시오.
- **`channel_not_found` 오류**: 채널 ID가 잘못되었습니다.
- **메시지가 나타나지 않음**
    - **OAuth & Permissions**에서 `chat:write` 범위가 추가되었는지 확인하십시오.
    - 범위가 변경된 후 앱이 작업 공간에 다시 설치되었는지 확인하십시오.
    - Circuit Breaker가 실제로 상태를 변경하고 있는지 확인하십시오.

## 다음 단계 {#next-steps}

- [PrometheusListener](prometheus.md): Metric 기반 모니터링 및 알림을 설정합니다.
- [LogListener](logging.md): 전환에 대한 상세 로깅을 구성합니다.
- [Listener 개요](index.md): 메인 Listener 페이지로 돌아갑니다.
