# Retry

Retry는 Circuit Breaker의 "쿨다운" 기간을 정의합니다. `OPEN` 상태에서 `HALF_OPEN` 상태로 전환하여 복구를 시도해야 하는 시점을 제어합니다.

| Retry 유형 | 전환 시점 | 적합한 경우 |
|---|---|---|
| **Always** | 즉시 | 즉각적인 Retry가 허용되는 중요하지 않은 서비스 |
| **Never** | 수동으로만 | 복구에 운영자의 수동 개입이 필요한 경우 |
| **Cooldown** | 고정 지연 후 | 일정 시간 대기 후 복구를 시도하기 원하는 경우 |
| **Backoff** | 지수적으로 증가하는 지연 후 | 반복적인 실패 후 더 오래 기다리는 적응형 접근 방식 |

---

## Always

회로가 열린 직후 `HALF_OPEN`으로 이동시킵니다. 이후 모든 호출에서 복구를 시도합니다.

!!! warning "주의해서 사용하십시오"
    `Always`는 많은 클라이언트가 동시에 Retry하여 복구 중인 서비스에 과부하를 주는 "동시다발적인 요청" 문제를 야기할 수 있으므로 위험할 수 있습니다. 실패가 매우 짧은 것으로 알려진 중요하지 않은 서비스에 가장 적합합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Always

# 일반적으로 권장되지 않습니다.
cb = CircuitBreaker(name="api", retry=Always(), ...)
```

---

## Never

수동으로 재설정될 때까지 회로를 `OPEN` 상태로 무기한 유지합니다. 서비스 복구에 사람의 개입이 필요할 때 유용합니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Never

cb = CircuitBreaker(name="api", retry=Never(), ...)

# 운영자는 서비스 복구 후 수동으로 브레이커를 재설정해야 합니다.
cb.reset()
```

---

## Cooldown

`HALF_OPEN`으로 이동하기 전에 고정된 `duration`(초 단위) 동안 기다립니다.

예측 가능한 시간 내에 복구가 예상되는 서비스일 경우 선택할 수 있습니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Cooldown

# 첫 번째 복구 시도 전에 60초 동안 기다립니다.
cb = CircuitBreaker(
    name="api",
    retry=Cooldown(duration=60.0),
    ...
)
```

---

## Backoff

각 연속적인 실패 후에 대기 시간을 지수적으로 증가시켜, 서비스가 복구할 시간을 더 많이 제공합니다.

대기 시간은 `initial * (multiplier ** consecutive_failures)`로 계산됩니다.

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.retries import Backoff

# 대기 시간은 10초에서 시작하여, 실패한 각 복구 시도 후에 두 배가 되며,
# 최대 300초로 제한됩니다.
cb = CircuitBreaker(
    name="api",
    retry=Backoff(
        initial=10.0,
        multiplier=2.0,
        max_duration=300.0
    ),
    ...
)
# 대기 시간 시퀀스
# 1차 시도 -> 10초
# 2차 시도 -> 20초
# 3차 시도 -> 40초
# 4차 시도 -> 80초
# 5차 시도 -> 160초
# 6차 이상 시도 -> 300초 (max_duration으로 제한)
```

---

## 올바른 Retry 선택

### 비교 {#comparison}

| 기능 | Always | Never | Cooldown | Backoff |
|---|---|---|---|---|
| **복구** | 즉시 | 수동 | 고정 지연 | 지수 지연 |
| **서비스 부하** | 높음 | 없음 | 중간 | 낮음 |
| **반복 실패 처리** | 아니요 | 해당 없음 | 아니요 | 예 |
| **복잡성** | 매우 간단 | 매우 간단 | 간단 | 중간 |
| **권장 여부** | 아니요 | 특수 사례용 | 좋은 기본값 | **권장** |

### `Always`는 언제 사용해야 하나요? {#choose-always}

실패가 극히 짧고 서비스가 많은 Retry 볼륨을 처리할 수 있는 것으로 알려진 중요하지 않은 서비스에만 사용합니다.

### `Never`는 언제 사용해야 하나요? {#choose-never}

서비스 복구에 수동 개입이 필요할 때 사용합니다. Circuit Breaker는 자체적으로 복구를 시도하지 않습니다.

- **사용 사례**: 계획된 배포 중이거나 서비스가 유지보수를 위해 중단되었을 때.

### `Cooldown`은 언제 사용해야 하나요? {#choose-cooldown}

간단한 기본값입니다. 서비스가 복구하는 데 걸리는 시간에 대한 일반적인 예측치가 있을 때 가장 좋습니다.

- **사용 사례**: 고정된 속도 제한 Window를 가진 외부 API와 같이 예측 가능한 복구 시간을 가진 서비스를 보호할 때.

### `Backoff`는 언제 사용해야 하나요? {#choose-backoff}

대부분의 사용 사례에서 **권장**됩니다. 반복적인 실패 시 복구할 시간을 더 많이 제공합니다.

- **사용 사례**: 다시 시작하거나 중단에서 복구하는 데 느릴 수 있는 중요한 하위 스트림 서비스를 보호할 때.

### 지터에 대한 참고 사항 {#using-jitter}

!!! tip "지터를 추가하세요"
    어플리케이션 서비스가 여러 인스턴스로 동작하는 경우, `Cooldown`과 `Backoff` 모두에 **jitter**를 추가하세요. 동시에 복구를 시도하는 "동시다발적인 요청" 시나리오를 방지하는 데 도움이 됩니다.

```python
from fluxgate.retries import Cooldown, Backoff

# 60초 쿨다운의 경우, 지터는 +/- 6초의 무작위 변동을 추가합니다 (54초에서 66초).
retry_cooldown = Cooldown(duration=60.0, jitter_ratio=0.1)

# 동일하게 백오프의 각 단계에도 적용됩니다.
retry_backoff = Backoff(initial=10.0, jitter_ratio=0.1)
```

## 다음 단계 {#next-steps}

- [Permits](permits.md): `HALF_OPEN` 복구 상태에서 허용되는 "프로브" 호출 수를 구성합니다.
- [Trippers](trippers.md): 회로가 트립되는 조건을 정의합니다.
