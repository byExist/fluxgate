# 설계 및 영감

이 문서는 Fluxgate의 핵심 설계 철학, 영감을 준 프로젝트, 그리고 주요 아키텍처 결정의 배경을 설명합니다.

## 이름

[플럭스게이트 자력계(fluxgate magnetometer)](https://en.wikipedia.org/wiki/Magnetometer#Fluxgate_magnetometer)는 포화 상태를 모니터링하고 임계값을 초과할 때 반응함으로써 자기장 변화를 감지하는 센서입니다. 이는 Circuit Breaker가 시스템 상태를 모니터링하고 실패 임계값을 초과할 때 "트립(trip)"하는 방식과 유사합니다.

## 영감

Fluxgate의 설계는 두 가지 훌륭한 프로젝트에서 크게 영감을 받았습니다.

### Resilience4j

[Resilience4j](https://resilience4j.readme.io/)는 Java용 경량, 인기 있는 결함 내성 라이브러리입니다. Fluxgate는 Resilience4j의 가장 중요한 개념인 서비스 상태 추적을 위한 **슬라이딩 윈도우(sliding windows)** 사용을 차용했습니다.

단순히 연속적인 실패만 추적하는 패턴과 달리, 슬라이딩 윈도우(카운트 기반 또는 시간 기반)는 최근 기간 동안 서비스 상태를 훨씬 더 정확하고 견고하게 평가합니다.

```python
# Fluxgate의 슬라이딩 윈도우 접근 방식은 Resilience4j에서 직접 영감을 받았습니다.
from fluxgate.windows import CountWindow, TimeWindow

window = CountWindow(size=100)  # 마지막 100개 호출을 추적합니다.
window = TimeWindow(size=60)    # 마지막 60초 동안의 호출을 추적합니다.
```

### Django REST Framework

[Django의 권한 시스템](https://www.django-rest-framework.org/api-guide/permissions/#how-permissions-are-determined)은 논리 연산자(`&`, `|`, `~`)와 결합된 **조합 가능한 객체**라는 훌륭하고 매우 유연한 패턴을 사용합니다.

<!--pytest.mark.skip-->

```python
# Django REST Framework에서는 간단한 권한 클래스를 조합하여 복잡한 규칙을 구축합니다.
from rest_framework.permissions import IsAuthenticated, IsAdminUser

class MyView(APIView):
    permission_classes = [IsAuthenticated & IsAdminUser]
```

Fluxgate는 `Tracker` 및 `Tripper` 컴포넌트에 이와 동일한 철학을 적용합니다. 사용자에게 복잡한 구성 스키마를 배우거나 번거로운 빌더 패턴을 사용하도록 강요하는 대신, 정교한 규칙을 만들기 위해 조합할 수 있는 간단하고 재사용 가능한 구성 요소를 제공합니다.

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# 간단한 Tripper를 조합하여 복잡한 트립 로직을 생성합니다.
tripper = MinRequests(10) & (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)
```

이 조합 가능한 접근 방식은 Fluxgate의 유연성의 핵심입니다.

## 설계 결정

Fluxgate는 다른 라이브러리와는 다른 두 가지 의도적인 설계 선택을 했습니다.

### 분산 상태 공유 없음

Fluxgate의 Circuit Breaker는 애플리케이션 프로세스 내에서만 상태를 관리합니다. 여러 프로세스나 서버 간에 상태를 공유하는 기능(예: Redis를 통한)은 내장되어 있지 않습니다.

이는 Circuit Breaker 패턴의 핵심 목적에 기반한 의도적인 결정입니다. 목표는 애플리케이션이 비정상적인 서비스를 반복적으로 호출하는 것을 방지하는 것입니다. 이는 분산 상태 없이도 효과적으로 달성할 수 있습니다.

- **독립적인 평가**: 하위 스트림 서비스가 비정상인 경우, 애플리케이션의 모든 인스턴스는 자체적인 실패 호출을 통해 이를 자연스럽게 감지합니다. 회로는 각 서버에서 독립적으로 올바르게 열릴 것입니다.
- **단순성 및 탄력성**: 분산 상태 저장소(예: Redis)에 대한 의존성을 추가하면 새로운 네트워크 의존성, 새로운 단일 실패 지점, 그리고 상당한 운영 복잡성이 발생합니다. 상태 저장소의 실패는 전체 Circuit Breaking 메커니즘을 비활성화시킬 수 있습니다.
- **성능**: 요청마다 회로 상태를 확인하기 위해 네트워크 호출을 하는 것보다 인프로세스 메모리에 의존하는 것이 훨씬 빠릅니다.

상태를 로컬로 유지함으로써 Fluxgate는 경량화되고 빠르며 탄력적이며, 외부 의존성이 없습니다.

### `CircuitBreaker`는 스레드 안전하지 않음

동시성 애플리케이션의 경우, Fluxgate는 `CircuitBreaker`와 함께 멀티스레딩이 아닌 `asyncio`와 함께 `AsyncCircuitBreaker`를 사용하는 것을 강력히 권장합니다.

표준 `CircuitBreaker` 클래스는 **스레드 안전하지 않습니다**. 이는 Python의 동시성 생태계의 현재 상태를 반영하는 의도적인 선택입니다.

- Python의 GIL(Global Interpreter Lock)로 인해 멀티스레딩은 CPU 바운드 코드를 병렬화하는 효과적인 방식이 아니며, `asyncio`에 비해 I/O 바운드 코드에 대한 이점도 제한적입니다.
- 현대 Python 생태계는 고성능 I/O 바운드 작업에 대해 `asyncio`를 압도적으로 수용했습니다. 웹 프레임워크(FastAPI, Starlette, aiohttp), 데이터베이스 드라이버(asyncpg), HTTP 클라이언트(httpx) 모두 `asyncio` 이벤트 루프를 기반으로 구축됩니다.
- `AsyncCircuitBreaker`는 이러한 현대 애플리케이션에서 Circuit Breaker를 사용하는 자연스럽고 관용적이며 가장 성능이 좋은 방법입니다.

## 함께 보기

- [비교](comparison.md): Fluxgate가 다른 Python 라이브러리와 어떻게 비교되는지 확인하세요.
- [컴포넌트 개요](../components/index.md): 라이브러리를 구성하는 컴포넌트에 대해 자세히 알아보세요.
