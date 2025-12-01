# Trippers

Tripper는 Window가 수집한 메트릭을 평가하여 circuit 상태 전환 여부를 판단합니다. 여러 조건을 논리 연산자(`&`, `|`)로 조합할 수 있습니다.

| Tripper 타입 | 조건 | 사용 사례 |
|-------------|------|----------|
| **Closed** | CLOSED 상태일 때 | 상태별 조건 분기 |
| **HalfOpened** | HALF_OPEN 상태일 때 | 상태별 조건 분기 |
| **MinRequests** | 최소 호출 수 충족 | 샘플 크기 보장 |
| **FailureRate** | 실패율 임계값 초과 | 에러율 기반 차단 |
| **AvgLatency** | 평균 지연시간 초과 | 성능 기반 차단 |
| **SlowRate** | 느린 호출 비율 초과 | 느린 응답 기반 차단 |

## Closed

CLOSED 상태일 때만 true를 반환합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import Closed, FailureRate

# CLOSED 상태에서만 실패율 검사
cb = CircuitBreaker(
    name="api",
    tripper=Closed() & FailureRate(0.5),
    ...
)
```

## HalfOpened

HALF_OPEN 상태일 때만 true를 반환합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import HalfOpened, FailureRate

# HALF_OPEN 상태에서는 더 엄격한 기준 적용
cb = CircuitBreaker(
    name="api",
    tripper=HalfOpened() & FailureRate(0.3),
    ...
)
```

## MinRequests

최소 호출 수를 충족할 때만 true를 반환합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import MinRequests, FailureRate

# 최소 10개 호출 후 실패율 검사
cb = CircuitBreaker(
    name="api",
    tripper=MinRequests(10) & FailureRate(0.5),
    ...
)
```

## FailureRate

실패율이 임계값을 초과할 때 true를 반환합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import FailureRate

# 실패율 50% 초과 시 circuit 열기
cb = CircuitBreaker(
    name="api",
    tripper=FailureRate(0.5),
    ...
)
```

## AvgLatency

평균 지연시간이 임계값을 초과할 때 true를 반환합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import AvgLatency

# 평균 응답시간 2초 초과 시 circuit 열기
cb = CircuitBreaker(
    name="api",
    tripper=AvgLatency(2.0),
    ...
)
```

## SlowRate

느린 호출 비율이 임계값을 초과할 때 true를 반환합니다.

!!! warning
    `SlowRate`를 사용하려면 CircuitBreaker의 `slow_threshold` 파라미터를 반드시 설정해야 합니다. 이 값보다 오래 걸리는 호출이 "느린 호출"로 간주됩니다. 기본값은 `inf`(무한대)이므로, 설정하지 않으면 모든 호출이 "빠른 호출"로 간주되어 SlowRate가 항상 0%가 됩니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import SlowRate

# 느린 호출 30% 초과 시 circuit 열기
cb = CircuitBreaker(
    name="api",
    tripper=SlowRate(0.3),
    slow_threshold=1.0,  # 1초 이상을 느린 호출로 간주
    ...
)
```

## 논리 연산자 {#operators}

Tripper는 논리 연산자로 조합할 수 있습니다.

### AND (`&`) - 모든 조건 만족

```python
from fluxgate.trippers import MinRequests, FailureRate

# 최소 10개 호출 AND 실패율 50% 이상
tripper = MinRequests(10) & FailureRate(0.5)
```

### OR (`|`) - 조건 중 하나 만족

```python
from fluxgate.trippers import FailureRate, SlowRate

# 실패율 50% 이상 OR 느린 호출 30% 이상
tripper = FailureRate(0.5) | SlowRate(0.3)
```

### 복잡한 조합

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# CLOSED: 최소 10개 호출 후 실패율 50%
# HALF_OPEN: 최소 5개 호출 후 실패율 30%
tripper = (
    (Closed() & MinRequests(10) & FailureRate(0.5)) |
    (HalfOpened() & MinRequests(5) & FailureRate(0.3))
)
```

## 선택 가이드 {#choosing-a-tripper}

### 비교 {#comparison}

| 특성 | Closed/HalfOpened | MinRequests | FailureRate | AvgLatency | SlowRate |
|-----|------------------|-------------|-------------|------------|--------------|
| **목적** | 상태별 조건 분기 | 샘플 크기 보장 | 에러율 검사 | 평균 성능 검사 | 느린 호출 검사 |
| **단독 사용** | 불가능 | 불가능 | 가능 | 가능 | 가능 |
| **일반적 조합** | 다른 Tripper와 AND | 다른 Tripper와 AND | MinRequests와 AND | MinRequests와 AND | MinRequests와 AND |

### MinRequests를 사용하세요 {#use-minrequests}

!!! tip "권장 사항"
    - 거의 모든 Tripper 조합에 포함
    - 샘플 크기가 작을 때 오판 방지
    - Window size의 10-20% 정도가 적당

**예시:**

```python
# Window size 100개, MinRequests 10개
tripper = MinRequests(10) & FailureRate(0.5)
```

### FailureRate vs AvgLatency vs SlowRate {#rate-vs-latency}

**FailureRate를 선택하세요:**

- 에러 발생 여부가 중요한 경우
- 명확한 실패 기준이 있는 경우

**AvgLatency를 선택하세요:**

- 전체 응답 시간 성능이 중요한 경우
- 평균적인 지연이 문제인 경우

**SlowRate를 선택하세요:**

- 느린 호출의 비율이 중요한 경우
- 특정 임계값(slow_threshold) 초과 비율을 제어하고 싶은 경우

### 여러 조건 조합하기 {#combining-conditions}

```python
from fluxgate.trippers import MinRequests, FailureRate, SlowRate

# 실패율 OR 느린 호출 비율
tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
```

## 다음 단계 {#next-steps}

- [Retries](retries.md) - Circuit이 열렸을 때 재시도 정책
- [Permits](permits.md) - HALF_OPEN 상태에서 호출 허용 정책
