# 설계와 영감

이 문서는 Fluxgate의 설계 결정과 영향을 준 프로젝트들을 설명합니다.

## 이름의 유래

[Fluxgate magnetometer](https://en.wikipedia.org/wiki/Magnetometer#Fluxgate_magnetometer)는 자기장의 변화를 감지하는 센서로, 포화 상태를 모니터링하고 임계값에서 반응합니다. Circuit breaker가 시스템 상태를 모니터링하고 임계값을 초과하면 작동하는 방식과 유사합니다.

## 영감

### Resilience4j

[Resilience4j](https://resilience4j.readme.io/)는 Netflix Hystrix에서 영감을 받은 Java용 경량 fault tolerance 라이브러리입니다. Fluxgate는 Resilience4j의 여러 핵심 개념을 차용했습니다.

Resilience4j는 단순한 연속 실패 카운팅 대신 슬라이딩 윈도우(개수 기반 또는 시간 기반)를 사용하여 호출 결과를 추적합니다. 이를 통해 서비스 상태를 더 정확하게 평가할 수 있습니다. Fluxgate도 이 방식을 채택했습니다.

```python
# Resilience4j에서 영감을 받은 Fluxgate의 슬라이딩 윈도우
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # 최근 100개 호출
window = TimeWindow(size=60)    # 최근 60초
```

### Django Permissions

[Django의 권한 시스템](https://docs.djangoproject.com/en/stable/topics/auth/default/#permissions)은 비트 연산자(`&`, `|`, `~`)를 사용하여 권한을 조합할 수 있습니다. 이 우아한 패턴이 Fluxgate의 조합 가능한 컴포넌트 설계에 영감을 주었습니다.

```python
# Django REST framework의 조합 가능한 권한
from rest_framework.views import APIView

class MyView(APIView):
    permission_classes = [IsAuthenticated & (IsAdminUser | IsStaff)]
```

Fluxgate는 Tripper와 Tracker에 동일한 패턴을 적용합니다:

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# 논리 연산자로 조합 가능한 tripper
tripper = MinRequests(10) & (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)
```

```python
from fluxgate.trackers import TypeOf

# 조합 가능한 tracker
tracker = TypeOf(ConnectionError, TimeoutError) & ~TypeOf(CancellationError)
```

이 접근 방식은 복잡한 설정 객체나 빌더 패턴 없이도 유연성을 제공합니다.

## 설계 결정

### 분산 상태 공유 미지원

Fluxgate는 분산 상태 공유(예: Redis 저장소)를 지원하지 않습니다. 각 CircuitBreaker 인스턴스는 단일 프로세스 내에서 상태를 관리합니다.

분산 상태는 circuit breaker 패턴의 근본적인 요구사항이 아닙니다. 이 패턴의 핵심 목적은 비정상 서비스에 대한 호출을 빠르게 중단하여 연쇄 장애를 방지하는 것입니다.

- 각 프로세스는 독립적으로 다운스트림 서비스의 상태를 평가할 수 있습니다. 서비스가 비정상이라면 모든 프로세스가 자체 실패를 통해 자연스럽게 이를 감지합니다.
- 분산 상태를 추가하면 네트워크 지연, 추가 장애 지점, 운영 복잡성이 발생합니다. 이러한 비용이 이점을 초과하는 경우가 많습니다.

### 스레드 안전하지 않음

`CircuitBreaker`는 스레드 안전하지 않습니다. 동시성 작업에는 asyncio와 함께 `AsyncCircuitBreaker`를 사용하세요.

현재 Python의 GIL(Global Interpreter Lock)로 인해 멀티스레드 Python 코드는 CPU 바운드 작업에서 진정한 병렬성을 달성하지 못합니다. 따라서 대부분의 I/O 바운드 Python 애플리케이션은 스레딩보다 asyncio에서 더 많은 이점을 얻습니다. 현대 Python 웹 프레임워크(FastAPI, Starlette, aiohttp)는 asyncio 기반이므로 `AsyncCircuitBreaker`가 자연스러운 선택입니다.

## 참고

- [비교](comparison.md) - 다른 Python 라이브러리와 비교
- [컴포넌트](../components/index.md) - 상세 컴포넌트 문서
