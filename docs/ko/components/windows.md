# Windows

Windows는 Circuit Breaker의 기억입니다. 최근 호출 결과(성공, 실패, 응답 시간 등)를 저장하고, `trippers`가 회로를 열지 여부를 결정하는 데 사용하는 Metric을 제공합니다.

Fluxgate는 두 가지 유형의 Window를 제공합니다.

| Window 유형 | 추적 방식 | 적합한 경우... |
|---|---|---|
| **CountWindow** | 마지막 N개 호출 | 안정적인 트래픽을 처리하며, 고정된 수의 최근 작업을 평가하려는 서비스에 적합합니다. |
| **TimeWindow** | 마지막 N초 | 가변적이거나 폭주하는 트래픽을 처리하며, 시간 기반 평가가 더 의미 있는 서비스에 적합합니다. |

---

## CountWindow

`CountWindow`는 가장 최근 N개의 호출을 추적합니다. 안정적이고 예측 가능한 트래픽 패턴을 가진 서비스에 훌륭한 선택입니다.

### 작동 방식 {#countwindow-how-it-works}

메모리에 고정 크기의 원형 버퍼를 유지합니다. 새 호출이 기록될 때, Window가 가득 찼으면 가장 오래된 호출을 덮어씁니다. 이는 Window가 항상 정확히 마지막 N개의 호출을 포함하도록 보장하여 일관된 평가 볼륨을 제공합니다.

### 기본 사용법 {#countwindow-basic}

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow

# 이 브레이커는 마지막 100개 호출을 기준으로 결정을 내립니다.
cb = CircuitBreaker(
    name="stable_api",
    window=CountWindow(size=100),
    ...
)
```

---

## TimeWindow

`TimeWindow`는 마지막 N초 동안 발생한 호출을 추적합니다. 호출 횟수보다 시간 기반 관점이 더 중요한 불규칙하거나 폭주하는 트래픽을 가진 서비스에 이상적입니다.

### 작동 방식 {#timewindow-how-it-works}

시간을 1초 단위의 버킷으로 나눕니다. 호출이 기록될 때 해당 결과는 현재 타임스탬프에 해당하는 버킷에 집계됩니다. 시간 Window를 벗어나는 오래된 버킷은 자동으로 만료되고 재사용됩니다.

### 기본 사용법 {#timewindow-basic}

<!--pytest.mark.skip-->

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import TimeWindow

# 이 브레이커는 마지막 60초 동안 발생한 호출을 기준으로 결정을 내립니다.
cb = CircuitBreaker(
    name="variable_traffic_api",
    window=TimeWindow(size=60),
    ...
)
```

## Window 선택

### 비교 {#comparison}

| 기능 | CountWindow | TimeWindow |
|---|---|---|
| **메모리 사용량** | 호출 수(size)에 비례합니다. | 초 단위(size)의 시간에 비례합니다. |
| **트래픽 스파이크** | 오래된 데이터가 빠르게 밀려날 수 있습니다. | 전체 기간 동안 데이터를 유지하여 폭주를 완화합니다. |
| **낮은 트래픽** | 전체 Metric 세트를 더 빨리 수집합니다. | 의미 있는 데이터를 수집하는 데 더 오래 걸릴 수 있습니다. |
| **평가 기준** | 고정된 수의 호출 | 고정된 시간 |
| **세분성** | 호출당 | 초당 |

### `CountWindow`는 언제 사용해야 하나요? {#choose-countwindow}

`CountWindow`는 다음과 같은 경우에 훌륭한 선택입니다.

- **안정적이고 예측 가능한 트래픽**: 호출 빈도가 크게 변동하지 않습니다.
- **메모리 효율성 필요**: 종종 동일한 범위에서 `TimeWindow`보다 적은 메모리를 사용합니다.
- **빠른 평가 필요**: 빠르게 채워져 의미 있는 Metric을 제공할 수 있습니다.

**일반적인 사용 사례**: 내부 마이크로서비스 간 통신, 백그라운드 처리 또는 배치 작업.

### `TimeWindow`는 언제 사용해야 하나요? {#choose-timewindow}

`TimeWindow`는 일반적으로 권장되며, 특히 다음과 같은 경우에 더 안전한 기본 선택입니다.

- **불규칙하거나 폭주하는 트래픽**: 갑작스러운 트래픽 급증을 유연하게 처리합니다.
- **시간 기반 정책 필요**: SLO는 시간(예: "모든 5분 Window에서 99.9% 가동 시간")을 기준으로 정의될 가능성이 높습니다.
- **실시간 응답성에 중점**: 호출 볼륨에 관계없이 항상 최근 기간의 결정에 기반합니다.

**일반적인 사용 사례**: 공개 API, 사용자 대면 서비스 또는 불안정한 외부 서비스 호출.

---

## Metric

두 Window 유형 모두 `trippers`에 대해 동일한 Metric을 제공합니다.

```python
from fluxgate.windows import CountWindow
from fluxgate.metric import Record

window = CountWindow(size=100)

# 수동으로 호출 기록
window.record(Record(success=True, duration=0.5))
window.record(Record(success=False, duration=1.2))

# 집계된 Metric 객체 가져오기
metric = window.get_metric()
print(f"Total calls: {metric.total_count}")
print(f"Failed calls: {metric.failure_count}")
print(f"Average duration: {metric.avg_duration}")
```

### 필드 속성

- `total_count`: Window에 기록된 총 호출 수.
- `failure_count`: 실패로 추적된 호출 수.
- `total_duration`: 모든 호출의 지속 시간 합계.
- `slow_count`: `slow_threshold`를 초과한 호출 수.
- `avg_duration`: 평균 응답 시간 (`total_duration / total_count`).
- `failure_rate`: 실패 호출 비율 (`failure_count / total_count`).
- `slow_rate`: 느린 호출 비율 (`slow_count / total_count`).

`avg_duration`, `failure_rate`, `slow_rate`는 total_count가 0일 경우 None입니다.

---

## 자동 리셋 {#auto-reset}

Circuit Breaker의 상태가 전환될 때(예: `OPEN` → `HALF_OPEN` 또는 `HALF_OPEN` → `CLOSED`) Window는 자동으로 Metric을 지웁니다. 이는 각 복구 시도와 각 새로운 `CLOSED` 기간이 깨끗한 상태로 시작되도록 보장합니다.

## 성능 고려 사항 {#performance}

| 작업 | CountWindow | TimeWindow |
|---|---|---|
| **메모리** | N은 `size`인 O(N) | N은 `size`인 O(N) |
| **`record()`** | O(1) | O(1) |
| **`get_metric()`** | O(1) | O(1) |

## 다음 단계 {#next-steps}

- [Trackers](trackers.md): 실패로 간주되는 요소를 정의합니다.
- [Trippers](trippers.md): 이 Metric을 사용하여 트립 로직을 구축합니다.
