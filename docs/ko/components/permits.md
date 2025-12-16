# Permits

Permit은 `HALF_OPEN` 상태에서 호출의 허용 여부를 결정합니다. Half Open으로 전환된 이후, 서비스로 통과될 수 있는 호출 수를 제어하여 갑작스러운 트래픽 폭주로 서비스가 과부하되는 것을 방지합니다.

| Permit 유형 | 동작 | 적합한 경우 |
|---|---|---|
| **All** | 모든 호출을 항상 허용 | 테스트 또는 트래픽 제한이 필요 없는 경우 |
| **Random** | 무작위로 고정된 비율의 호출을 허용 | 트래픽을 제한하는 확률적인 방식 |
| **RampUp** | 허용된 호출의 비율을 점진적으로 증가 | 트래픽을 부드럽게 재도입하는 방식 |

---

## All

모든 호출을 무조건 통과시킵니다.

### 작동 방식 {#all-how-it-works}

`All`은 모든 호출에 대해 `True`를 반환하여 `HALF_OPEN` 상태에서 100%의 트래픽을 허용합니다. 이는 주로 테스트 시나리오에서 유용하거나, 상태 전환 제어를 `tripper`에만 의존하려는 경우에 사용합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import All

# HALF_OPEN 상태에서 모든 호출을 통과시킵니다.
cb = CircuitBreaker(
    name="api",
    permit=All(),
    ...
)
```

---

## Random

고정된 확률로 호출을 통과시킵니다.

### 작동 방식 {#random-how-it-works}

`HALF_OPEN` 상태에 도달하는 모든 호출에 대해 `Random`은 난수를 생성하고, 구성된 `ratio` 내에 있으면 호출을 허용합니다.

- `Random(ratio=0.1)`은 대략 10%의 호출을 허용합니다.
- `Random(ratio=0.8)`은 대략 80%의 호출을 허용합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import Random

# HALF_OPEN 상태에서 대략 50%의 호출을 통과시킵니다.
cb = CircuitBreaker(
    name="api",
    permit=Random(ratio=0.5),
    ...
)
```

---

## RampUp

시간이 지남에 따라 허용률을 점진적으로 증가시켜 더 부드럽고 온건한 복구를 제공합니다. 대부분의 케이스에 권장됩니다.

### 작동 방식 {#rampup-how-it-works}

`HALF_OPEN` 상태에 진입한 이후 경과된 시간을 기반으로, 설정된 `duration` 동안 `initial` 값에서 `final` 값까지 허용되는 트래픽 비율을 선형적으로 증가시킵니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.permits import RampUp

# 10%의 트래픽을 허용하는 것으로 시작하여 60초 동안 80%까지 점진적으로 증가시킵니다.
cb = CircuitBreaker(
    name="api",
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

**예시 진행:** `RampUp(initial=0.1, final=0.8, duration=60.0)`의 경우

- **0초 시점**: 호출의 10%가 허용됩니다.
- **15초 시점**: 호출의 27.5%가 허용됩니다.
- **30초 시점**: 호출의 45%가 허용됩니다.
- **60초 시점(이후)**: 비율은 `final` 값인 80%로 제한됩니다.

---

## 올바른 Permit 선택

### 비교 {#comparison}

| 기능 | All | Random | RampUp |
|---|---|---|---|
| **복잡성** | 매우 간단 | 간단 | 중간 |
| **허용률** | 100% | 일정 | 시간 경과에 따라 증가 |
| **복구 방식** | 제한 없음 | 즉시 고정 비율 | 점진적 증가 |
| **로드 스파이크 위험** | 가장 높음 | 높음 (높은 비율에서) | 매우 낮음 |
| **권장** | 테스트 전용 | 간단한 경우 | **권장** |

### `Random`은 언제 사용해야 하나요? {#choose-random}

`Random`은 일정한 속도로 복구 테스트를 즉시 시작해야 하고 하위 스트림 서비스에 과부하를 주는 것에 대해 걱정하지 않는 간단한 사용 사례에 가장 적합합니다.

**권장 설정:**

```python
from fluxgate.permits import Random

# 보수적 (안정성 우선)
permit = Random(ratio=0.3)

# 공격적 (빠른 복구 우선)
permit = Random(ratio=0.8)
```

### `RampUp`은 언제 사용해야 하나요? {#choose-rampup}

`RampUp`은 대부분의 사용 사례에서 **권장**됩니다. 트래픽을 천천히 재도입하여 서비스가 캐시를 워밍업하고 연결을 재설정하며 스케일업할 시간을 제공함으로써 가장 안전한 복구 경로를 제공합니다.

**권장 설정:**

```python
from fluxgate.permits import RampUp

# 보수적 복구
permit = RampUp(initial=0.1, final=0.5, duration=120.0)

# 공격적 복구
permit = RampUp(initial=0.5, final=1.0, duration=30.0)
```

---

## Retry와의 관계 {#relationship-with-retry}

`retry` 및 `permit`은 함께 작동하여 완전한 복구 프로세스를 정의합니다.

- **Retry**: Half Open 상태로의 전환 시점을 결정합니다.
- **Permit**: Half Open 상태에서 요청의 허용 여부를 결정합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff
from fluxgate.permits import RampUp

cb = CircuitBreaker(
    name="api",
    retry=Backoff(initial=10.0, multiplier=2.0),
    permit=RampUp(initial=0.1, final=0.8, duration=60.0),
    ...
)
```

**복구 흐름은 다음과 같습니다:**

1. `tripper` 조건이 충족되고 회로가 `OPEN` 상태로 전환됩니다.
2. `retry`가 일정 시간 대기합니다. `Backoff(initial=10.0)`을 사용하면 10초 동안 기다립니다.
3. 10초 후 회로가 `HALF_OPEN`으로 전환됩니다.
4. 이제 `permit`이 동작합니다. 다음 60초 동안 허용되는 호출의 비율을 10%에서 80%까지 점진적으로 증가시킵니다.
5. 이 시간 동안 `tripper`의해 실패로 판단되면 `OPEN`으로 다시 trip되고 `retry` 카운터가 증가합니다(다음 대기 시간은 20초가 됩니다).
6. 성공하면 회로는 `CLOSED`로 다시 전환되고 정상 작동이 재개됩니다.

## 다음 단계 {#next-steps}

- [Listeners](listeners/index.md): 상태 변경을 모니터링하고 알림을 받습니다.
- [Circuit Breaker 개요](../circuit-breaker.md): 모든 컴포넌트가 어떻게 함께 작동하는지 확인하세요.
