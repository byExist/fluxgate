# Tripper

Tripper는 Circuit Breaker의 상태 전환 조건을 제어합니다. `Window`에서 제공하는 Metric을 기반으로 회로가 상태를 변경해야 하는지(예: `CLOSED`에서 `OPEN`으로) 결정합니다. 각 Tripper 컴포넌트를 논리 연산자(`&`, `|`)와 결합함으로써, 브레이커가 언제 트립해야 하는지에 대한 규칙을 정의할 수 있습니다.

| Tripper 유형 | 조건 | 사용 사례 |
|---|---|---|
| **Closed** / **HalfOpened** | 회로가 특정 상태인지 확인합니다. | 특정 상태에서만 적용되는 조건을 구성합니다. |
| **MinRequests** | 호출 수가 최소값을 초과하는지 확인합니다. | 통계적으로 유의미하지 않은 적은 수의 호출로 인해 트립되는 것을 방지합니다. |
| **FailureRate** | 실패율이 너무 높은지 확인합니다. | 오류율이 허용할 수 없을 정도로 높아지면 트립합니다. |
| **AvgLatency** | 평균 응답 시간이 너무 느린지 확인합니다. | 전반적인 성능이 저하될 때 트립합니다. |
| **SlowRate** | 느린 호출의 비율이 너무 높은지 확인합니다. | 느린 요청의 비율을 기반으로 트립합니다. |
| **FailureStreak** | 연속 실패 횟수를 확인합니다. | 콜드 스타트 또는 서비스 전면 장애 시 빠르게 트립합니다. |

---

## 상태 기반 Tripper

이 Tripper는 Circuit Breaker의 현재 상태를 확인하여 `CLOSED` 또는 `HALF_OPEN` 상태에서만 적용되는 규칙을 만들 수 있도록 합니다.

- `Closed()`: 회로가 `CLOSED` 상태일 때만 `True`를 반환합니다.
- `HalfOpened()`: 회로가 `HALF_OPEN` 상태일 때만 `True`를 반환합니다.

이들은 거의 항상 다른 조건을 범위 지정하기 위해 `&` 연산자와 함께 사용됩니다.

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import Closed, HalfOpened, FailureRate

# CLOSED 및 HALF_OPEN 상태에 대해 다른 실패율 임계값을 사용합니다.
tripper = (
    (Closed() & FailureRate(0.5)) |
    (HalfOpened() & FailureRate(0.3))
)
```

---

## 메트릭 기반 Tripper

이 Tripper는 `window`가 수집한 메트릭을 평가합니다.

### MinRequests

`MinRequests(count)`는 Window가 최소한 `count` 호출을 기록한 후에만 `True`를 반환합니다. 이는 통계적으로 중요하지 않은 적은 수의 실패(예: 2개 호출 중 1개 실패는 50% 실패율이지만, 통계적으로 충분한 데이터가 아님)로 인해 브레이커가 트립되는 것을 방지하는 데 매우 중요합니다.

```python
from fluxgate.trippers import MinRequests, FailureRate

# 최소 10개의 호출이 기록될 때까지 브레이커는 트립되지 않습니다.
tripper = MinRequests(10) & FailureRate(0.5)
```

### FailureRate

`FailureRate(rate)`는 실패한 호출 대 총 호출 수의 비율이 `rate`를 초과하면(`0.5`는 50%) `True`를 반환합니다.

```python
from fluxgate.trippers import FailureRate

# 호출의 50% 이상이 실패하는 경우 트립됩니다.
tripper = FailureRate(0.5)
```

### AvgLatency

`AvgLatency(seconds)`는 Window 내 모든 호출의 평균 응답 시간이 `seconds`를 초과하면 `True`를 반환합니다.

```python
from fluxgate.trippers import AvgLatency

# 평균 응답 시간이 2초를 초과하면 트립됩니다.
tripper = AvgLatency(2.0)
```

### SlowRate

`SlowRate(rate)`는 느린 호출의 비율이 `rate`를 초과하면 `True`를 반환합니다. 호출 시간이 `CircuitBreaker`의 `slow_threshold` 매개변수(초 단위)를 초과하면 "느린" 호출로 간주됩니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.trippers import SlowRate

# 호출의 30% 이상이 "느린" 경우 트립됩니다.
cb = CircuitBreaker(
    name="api",
    tripper=SlowRate(0.3),
    slow_threshold=1.0,  # 1초 이상 걸리는 호출은 느린 것으로 간주됩니다.
    ...
)
```

### FailureStreak

`FailureStreak(count)`는 연속 실패 횟수가 `count`에 도달하면 `True`를 반환합니다. 콜드 스타트 시 또는 외부 서비스가 완전히 다운되었을 때 빠르게 장애를 감지하는 데 유용합니다.

```python
from fluxgate.trippers import FailureStreak, MinRequests, FailureRate

# 5회 연속 실패 후 트립
tripper = FailureStreak(5)

# FailureRate와 결합하여 종합적인 보호:
# - 5회 연속 실패 시 빠른 트립 (콜드 스타트 보호)
# - 또는 20개 요청 후 50% 실패율 시 통계적 트립
tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))
```

---

## 논리 연산자를 이용한 Tripper 결합 {#operators}

논리 연산자를 사용하여 Tripper를 결합함으로써 강력하고 정밀한 규칙을 만들 수 있습니다.

### AND (`&`)

`&` 연산자는 **모든** 조건이 참이어야 합니다. Tripper를 결합하는 가장 일반적인 방법입니다.

```python
from fluxgate.trippers import MinRequests, FailureRate

# Window에 최소 10개의 요청이 있고 실패율이 50%를 초과하는 경우에만 trip됩니다.
tripper = MinRequests(10) & FailureRate(0.5)
```

### OR (`|`)

`|` 연산자는 **어느 하나라도** 조건이 참이어야 합니다.

```python
from fluxgate.trippers import FailureRate, SlowRate

# 실패율이 50%를 초과하거나 느린 호출 비율이 30%를 초과하는 경우 trip됩니다.
tripper = FailureRate(0.5) | SlowRate(0.3)
```

### 복합 예제

다음은 `CLOSED` 및 `HALF_OPEN` 상태에 대해 다른 규칙을 만드는 방법입니다.

```python
from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate

# - 상태가 CLOSED이면, 최소 10개의 요청이 있고 실패율이 50%를 초과할 때 trip됩니다.
# - 또는 상태가 HALF_OPEN이면, 최소 5개의 요청이 있고 실패율이 30%를 초과할 때 trip됩니다.
tripper = (
    (Closed() & MinRequests(10) & FailureRate(0.5)) |
    (HalfOpened() & MinRequests(5) & FailureRate(0.3))
)
```

---

## 올바른 Tripper 선택하기

### 비교 {#comparison}

| 기능 | `Closed`/`HalfOpened` | `MinRequests` | `FailureRate` | `AvgLatency` | `SlowRate` | `FailureStreak` |
|---|---|---|---|---|---|---|
| **목적** | 특정 상태에 규칙 적용 | 의미 있는 샘플 크기 보장 | 실패한 호출의 비율 확인 | 평균 성능 확인 | 느린 호출의 비율 확인 | 연속 실패 시 빠른 트립 |
| **단독 사용** | X | X | O | O | O | O |

### 항상 `MinRequests` 사용하기 {#use-minrequests}

!!! tip "강력 추천"
    거의 모든 Tripper 조합에 `MinRequests`를 포함해야 합니다. 이는 회로가 통계적으로 유의미하지 않은 적은 수의 호출 샘플을 기반으로 성급한 결정을 내리는 것을 방지합니다. Window 크기의 10-20% 정도의 값이 좋은 시작점입니다.

```python
from fluxgate.trippers import MinRequests, FailureRate

# CountWindow(size=100)의 경우, MinRequests를 10-20으로 설정하는 것이 합리적입니다.
tripper = MinRequests(10) & FailureRate(0.5)
```

### `FailureRate` vs. `AvgLatency` vs. `SlowRate` {#rate-vs-latency}

- 명시적인 오류(예외)를 가장 중요하게 생각한다면 **`FailureRate`를 선택하세요**. 가장 일반적이고 직관적인 선택입니다.

- 전반적인 속도 저하로부터 보호하고 싶을 때는 **`AvgLatency`를 선택하세요**. 주의: 몇 개의 매우 느린 호출이 평균을 왜곡할 수 있습니다.

- 이상치(outlier)로부터 보호하고 싶을 때는 **`SlowRate`를 선택하세요**. 단 하나의 극도로 느린 호출에 덜 민감하기 때문에 `AvgLatency`보다 종종 더 견고합니다. 이는 평균적인 느림이 아닌, 느린 호출의 *비율*을 측정합니다.

### 종합하기 {#combining-conditions}

일반적으로 여러 조건을 결합하여 사용하기를 권장합니다.

```python
from fluxgate.trippers import MinRequests, FailureRate, SlowRate

# 최소 10개의 호출 이후, 실패율이 50%를 초과하거나 느린 호출 비율이 30%를 초과하는 경우 trip됩니다.
tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
```

## 다음 단계 {#next-steps}

- [Retries](retries.md): `OPEN` 상태에서 복구하기 위한 정책을 정의합니다.
- [Permits](permits.md): `HALF_OPEN` 상태에서 복구를 테스트하는 방법을 구성합니다.
