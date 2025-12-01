# Retries

Retry는 OPEN 상태에서 HALF_OPEN 상태로 전환할 시점을 결정합니다.

| Retry 타입 | 전환 시점 | 사용 사례 |
|-----------|----------|----------|
| **Always** | 즉시 | 빠른 복구 시도 |
| **Never** | 전환 불가 | 수동 복구 |
| **Cooldown** | 고정 대기 시간 후 | 일정 시간 대기 |
| **Backoff** | 지수 백오프 | 반복 실패 시 대기 시간 증가 |

## Always

매 호출마다 즉시 HALF_OPEN으로 전환을 시도합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Always

# 즉시 복구 시도
cb = CircuitBreaker(
    name="api",
    retry=Always(),
    ...
)
```

## Never

수동으로 reset()을 호출할 때까지 OPEN 상태를 유지합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Never

# 수동 복구만 허용
cb = CircuitBreaker(
    name="api",
    retry=Never(),
    ...
)

# 수동 복구
cb.reset()
```

## Cooldown

고정된 대기 시간 후 HALF_OPEN으로 전환합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Cooldown

# 60초 대기 후 복구 시도
cb = CircuitBreaker(
    name="api",
    retry=Cooldown(duration=60.0),
    ...
)

# jitter 추가로 thundering herd 방지
cb = CircuitBreaker(
    name="api",
    retry=Cooldown(duration=60.0, jitter_ratio=0.1),  # ±10% 랜덤
    ...
)
```

## Backoff

재시도 횟수에 따라 대기 시간이 지수적으로 증가합니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff

# 10초부터 시작, 2배씩 증가, 최대 300초
cb = CircuitBreaker(
    name="api",
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0
    ),
    ...
)
# 재시도 횟수별 대기 시간:
# 0회 → 10초
# 1회 → 20초
# 2회 → 40초
# 3회 → 80초
# 4회 → 160초
# 5회 이상 → 300초

# jitter 추가
cb = CircuitBreaker(
    name="api",
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0,
        jitter_ratio=0.1  # ±10% 랜덤
    ),
    ...
)
```

## 선택 가이드 {#choosing-a-retry}

### 비교 {#comparison}

| 특성 | Always | Never | Cooldown | Backoff |
|-----|--------|-------|----------|---------|
| **복구 속도** | 즉시 | 불가능 | 고정 시간 | 점진적 증가 |
| **서비스 부하** | 높음 | 없음 | 중간 | 낮음 |
| **반복 실패 대응** | 없음 | N/A | 없음 | 우수 |
| **사용 복잡도** | 단순 | 단순 | 단순 | 중간 |

### Always를 선택하세요 {#choose-always}

**적합한 경우:**

- 일시적 장애가 대부분인 경우
- 빠른 복구가 중요한 경우
- 서비스 부하가 문제되지 않는 경우

**예시:** 네트워크 순간 단절, 일시적 DNS 오류

### Never를 선택하세요 {#choose-never}

**적합한 경우:**

- 수동 개입이 필요한 경우
- 모니터링 후 결정이 필요한 경우

**예시:** 배포 중단, 점검 중인 서비스

### Cooldown을 선택하세요 {#choose-cooldown}

**적합한 경우:**

- 예측 가능한 복구 시간
- 고정된 대기 시간으로 충분한 경우
- Thundering herd 방지 필요 (jitter 사용)

**예시:** 외부 API rate limit, 스케줄된 점검

### Backoff를 선택하세요 {#choose-backoff}

**적합한 경우:**

- 반복 실패 가능성이 높은 경우
- 서비스 부하를 점진적으로 줄여야 하는 경우
- 복구 시간을 예측하기 어려운 경우

**예시:** 장애 복구 중인 서비스, 과부하 상태

### Jitter 사용 {#using-jitter}

**Jitter를 추가하세요:**

- 다수의 circuit breaker가 동시에 복구를 시도하는 경우
- Thundering herd 문제를 방지하고 싶은 경우

```python
# jitter_ratio=0.1 → ±10% 랜덤
# duration=60.0 → 실제 대기: 54~66초
retry = Cooldown(duration=60.0, jitter_ratio=0.1)
```

## 다음 단계 {#next-steps}

- [Permits](permits.md) - HALF_OPEN 상태에서 호출 허용 정책
- [Trippers](trippers.md) - Circuit 상태 전환 조건
