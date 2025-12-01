# Permits

HALF_OPEN 상태에서 호출 허용 여부를 제어합니다. Circuit이 복구를 시도할 때 트래픽을 점진적으로 허용하여 안정적인 복구를 돕습니다.

| Permit 타입 | 동작 방식 | 사용 사례 |
|------------|----------|----------|
| **Random** | 고정된 확률로 랜덤 허용 | 단순한 트래픽 제한 |
| **RampUp** | 시간에 따라 점진적 증가 | 부드러운 트래픽 복구 |

## Random

고정된 확률로 호출을 랜덤하게 허용합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import Random

# HALF_OPEN 상태에서 50% 확률로 호출 허용
cb = CircuitBreaker(
    name="api",
    permit=Random(ratio=0.5),
    ...
)
```

### 동작 방식 {#random-how-it-works}

- 각 호출마다 독립적으로 확률 계산
- `ratio` 값이 허용 확률 결정 (0.0 ~ 1.0)
- 시간과 무관하게 일정한 비율 유지

### 사용 시나리오 {#random-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import Random

# 보수적 복구: 10%만 허용
cb = CircuitBreaker(
    name="conservative_api",
    permit=Random(ratio=0.1),
    ...
)

# 적극적 복구: 80% 허용
cb = CircuitBreaker(
    name="aggressive_api",
    permit=Random(ratio=0.8),
    ...
)
```

## RampUp

시간에 따라 허용 비율을 점진적으로 증가시킵니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import RampUp

# 10%에서 시작하여 60초에 걸쳐 80%까지 증가
cb = CircuitBreaker(
    name="api",
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

### 동작 방식 {#rampup-how-it-works}

- HALF_OPEN 전환 시각부터 경과 시간 측정
- 선형으로 허용 비율 증가: `initial + (final - initial) × (elapsed / duration)`
- `duration` 경과 후에는 `final` 비율 유지

**예시: initial=0.1, final=0.8, duration=60초**

- 0초: 10% 허용
- 15초: 27.5% 허용
- 30초: 45% 허용
- 45초: 62.5% 허용
- 60초 이후: 80% 허용

### 사용 시나리오 {#rampup-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import RampUp

# 점진적 복구가 필요한 외부 API
cb = CircuitBreaker(
    name="external_api",
    permit=RampUp(initial=0.1, final=0.9, duration=120.0),
    ...
)

# 빠른 복구가 가능한 내부 서비스
cb = CircuitBreaker(
    name="internal_service",
    permit=RampUp(initial=0.3, final=1.0, duration=30.0),
    ...
)
```

## 선택 가이드 {#choosing-a-permit}

### 비교 {#comparison}

| 특성 | Random | RampUp |
|-----|--------|--------|
| **복잡도** | 단순 | 중간 |
| **허용 비율** | 일정 | 시간에 따라 증가 |
| **복구 속도** | 즉시 고정 비율 | 점진적 증가 |
| **부하 급증** | 가능 (높은 ratio 사용 시) | 최소화 |
| **사용 사례** | 단순한 트래픽 제한 | 안정적인 점진적 복구 |

### Random을 선택하세요 {#choose-random}

**적합한 경우:**

- 단순한 트래픽 제어 필요
- 즉시 일정한 비율로 복구
- 부하 급증이 문제되지 않는 경우

**예시:** 내부 서비스, 복구 시간이 중요한 경우

**권장 설정:**

```python
# 보수적 (안정성 우선)
permit = Random(ratio=0.3)

# 균형적
permit = Random(ratio=0.5)

# 적극적 (빠른 복구 우선)
permit = Random(ratio=0.8)
```

### RampUp을 선택하세요 {#choose-rampup}

**적합한 경우:**

- 점진적인 트래픽 증가 필요
- 부하 급증 방지 중요
- 외부 서비스 보호 필요

**예시:** 외부 API, 데이터베이스, 부하에 민감한 서비스

**권장 설정:**

```python
# 보수적 복구
permit = RampUp(initial=0.1, final=0.5, duration=120.0)

# 균형적 복구
permit = RampUp(initial=0.2, final=0.8, duration=60.0)

# 적극적 복구
permit = RampUp(initial=0.5, final=1.0, duration=30.0)
```

## Retry와의 관계 {#relationship-with-retry}

Permit과 Retry는 함께 작동하여 복구 전략을 결정합니다:

- **Retry**: OPEN → HALF_OPEN 전환 시점 결정
- **Permit**: HALF_OPEN 상태에서 호출 허용 비율 결정

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

# 재시도는 점진적으로, 허용은 천천히 증가
cb = CircuitBreaker(
    name="api",
    retry=Backoff(initial=10.0, multiplier=2.0, max_duration=300.0),
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

**동작 흐름:**

1. Circuit이 OPEN 상태로 전환
2. `Retry`가 대기 시간 결정 (예: 10초)
3. 10초 후 HALF_OPEN으로 전환
4. `Permit`이 호출 허용 여부 결정 (예: 시작 10%, 점진적 증가)
5. 성공하면 CLOSED로, 실패하면 다시 OPEN으로

## 다음 단계 {#next-steps}

- [Listeners](listeners/index.md) - Circuit 상태 변화 모니터링
- [CircuitBreaker](../circuit-breaker.md) - 전체 설정 통합
