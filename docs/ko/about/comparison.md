# 다른 라이브러리와 비교

이 페이지에서는 Fluxgate와 다른 Python circuit breaker 라이브러리를 비교하여 상황에 맞는 선택을 돕습니다.

## 개요

| 라이브러리 | Python | License |
|-----------|--------|---------|
| [![circuitbreaker](https://img.shields.io/github/stars/fabfuel/circuitbreaker?label=circuitbreaker&logo=github)](https://github.com/fabfuel/circuitbreaker) | ![Python](https://img.shields.io/pypi/pyversions/circuitbreaker) | ![License](https://img.shields.io/github/license/fabfuel/circuitbreaker) |
| [![pybreaker](https://img.shields.io/github/stars/danielfm/pybreaker?label=pybreaker&logo=github)](https://github.com/danielfm/pybreaker) | ![Python](https://img.shields.io/pypi/pyversions/pybreaker) | ![License](https://img.shields.io/github/license/danielfm/pybreaker) |
| [![aiobreaker](https://img.shields.io/github/stars/arlyon/aiobreaker?label=aiobreaker&logo=github)](https://github.com/arlyon/aiobreaker) | ![Python](https://img.shields.io/pypi/pyversions/aiobreaker) | ![License](https://img.shields.io/github/license/arlyon/aiobreaker) |
| [![pycircuitbreaker](https://img.shields.io/github/stars/etimberg/pycircuitbreaker?label=pycircuitbreaker&logo=github)](https://github.com/etimberg/pycircuitbreaker) | ![Python](https://img.shields.io/pypi/pyversions/pycircuitbreaker) | ![License](https://img.shields.io/github/license/etimberg/pycircuitbreaker) |

## 기능 비교

| 기능 | Fluxgate | circuitbreaker | pybreaker | aiobreaker |
|-----|:--------:|:--------------:|:---------:|:----------:|
| **동기 지원** | Yes | Yes | Yes | No |
| **비동기 지원** | Yes (asyncio) | Yes | Tornado만 | Yes (asyncio) |
| **트리거 조건** | 실패율 | 연속 실패 | 연속 실패 | 연속 실패 |
| **슬라이딩 윈도우** | Yes (Count/Time) | No | No | No |
| **조합 가능한 조건** | Yes (`&`, `\|`) | No | No | No |
| **지연시간 기반 트리거** | Yes (AvgLatency, SlowRate) | No | No | No |
| **Fallback** | Yes | Yes | No | No |
| **Redis 저장소** | No | No | Yes | Yes |
| **리스너/모니터링** | Yes (Log, Prometheus, Slack) | Yes (Monitor) | Yes | Yes |
| **타입 힌트** | 완전 | 부분 | 부분 | 부분 |
| **HALF_OPEN 제어** | Yes (Permit) | 1회 테스트 | success_threshold | 1회 테스트 |

## 주요 차이점

### 트리거 조건

대부분의 circuit breaker 라이브러리는 **연속 실패 횟수**를 사용합니다:

```python
# circuitbreaker / pybreaker
# 5회 연속 실패 후 OPEN
@circuit(failure_threshold=5)
def call_api():
    ...
```

Fluxgate는 **슬라이딩 윈도우 내 실패율**을 사용합니다:

```python
# Fluxgate
# 최근 100개 호출 중 실패율 50% 초과 시 OPEN
cb = CircuitBreaker(
    window=CountWindow(size=100),
    tripper=MinRequests(10) & FailureRate(0.5),
    ...
)
```

이 접근 방식의 장점:

- 단 한 번의 성공으로 실패 카운트가 리셋되지 않음
- 간헐적 실패를 더 잘 처리
- 더 정확한 서비스 상태 평가

### 조합 가능한 조건

Fluxgate는 논리 연산자로 여러 조건을 조합할 수 있습니다:

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate, SlowRate

# 상태별로 다른 임계값 적용
tripper = MinRequests(10) & (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)

# 여러 트리거 조건 조합
tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
```

### 지연시간 기반 트리거

Fluxgate는 에러뿐만 아니라 응답 시간을 기반으로도 circuit을 열 수 있습니다:

```python
from fluxgate.trippers import AvgLatency, SlowRate

# 평균 지연시간 2초 초과 시 OPEN
tripper = MinRequests(10) & AvgLatency(2.0)

# 느린 호출(1초 초과)이 30% 이상이면 OPEN
cb = CircuitBreaker(
    tripper=MinRequests(10) & SlowRate(0.3),
    slow_threshold=1.0,  # 1초
    ...
)
```

### 점진적 복구

Fluxgate는 HALF_OPEN 상태에서 세밀한 복구 제어를 제공합니다:

```python
from fluxgate.permits import RampUp

# 60초에 걸쳐 트래픽을 10%에서 80%로 점진적 증가
cb = CircuitBreaker(
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

## 라이브러리 선택 가이드

### Fluxgate를 선택하세요

- 연속 실패가 아닌 실패율 기반 트리거가 필요할 때
- 지연시간 기반 circuit breaking이 필요할 때
- 복잡한 트리거 조건을 조합해야 할 때
- 현대적인 asyncio 애플리케이션을 구축할 때
- 완전한 타입 힌트와 IDE 지원이 중요할 때

### circuitbreaker를 선택하세요

- 간단하고 검증된 솔루션이 필요할 때
- 연속 실패 카운팅으로 충분할 때
- 최소한의 설정을 원할 때

### pybreaker를 선택하세요

- 분산 상태를 위한 Redis 저장소가 필요할 때
- Tornado로 비동기를 사용할 때
- `success_threshold` 기능이 필요할 때

### aiobreaker를 선택하세요

- asyncio와 함께 Redis 저장소가 필요할 때
- pybreaker의 기능 세트로 충분할 때

## 참고

- [Circuit Breaker](../circuit-breaker.md) - 핵심 개념과 사용법
- [컴포넌트](../components/index.md) - 상세 컴포넌트 문서
