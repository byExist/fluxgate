# Windows

Window는 최근 호출의 성공/실패, 응답 시간 등을 추적하여 tripper가 circuit 상태를 결정할 수 있도록 메트릭을 제공합니다.

| Window 타입 | 추적 방식 | 사용 사례 |
|-------------|----------|----------|
| **CountWindow** | 최근 N개 호출 | 고정된 호출 수 기반 평가 |
| **TimeWindow** | 최근 N초 | 시간 기반 평가, 트래픽 변동 대응 |

## CountWindow

고정된 개수의 최근 호출을 추적합니다.

### 기본 사용법 {#countwindow-basic}

```python
from fluxgate.windows import CountWindow

# 최근 100개 호출 추적
window = CountWindow(size=100)
```

### 동작 방식 {#countwindow-how-it-works}

- 최근 N개 호출만 메모리에 유지
- 윈도우가 가득 차면 가장 오래된 기록 제거
- 호출 수가 적을 때도 일관된 평가 가능

### 사용 시나리오 {#countwindow-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import CountWindow

# 안정적인 트래픽 패턴을 가진 API
cb = CircuitBreaker(
    name="stable_api",
    window=CountWindow(size=100),  # 최근 100개 호출 평가
    ...
)
```

## TimeWindow

시간 기반으로 최근 N초의 호출을 추적합니다.

### 기본 사용법 {#timewindow-basic}

```python
from fluxgate.windows import TimeWindow

# 최근 60초 추적
window = TimeWindow(size=60)
```

### 동작 방식 {#timewindow-how-it-works}

- 시간을 1초 단위 버킷으로 분할
- 각 버킷은 해당 초의 모든 호출 집계
- 오래된 버킷은 자동으로 만료되고 재사용

### 사용 시나리오 {#timewindow-use-cases}

```python
from fluxgate import CircuitBreaker
from fluxgate.windows import TimeWindow

# 트래픽 변동이 큰 API
cb = CircuitBreaker(
    name="variable_traffic_api",
    window=TimeWindow(size=60),  # 최근 60초 평가
    ...
)
```

## 선택 가이드 {#choosing-a-window}

### 비교 {#comparison}

| 특성 | CountWindow | TimeWindow |
|-----|-------------|------------|
| **추적 방식** | 최근 N개 호출 | 최근 N초 |
| **메모리 사용** | 정확히 N개 기록 | N개 버킷 (1초 단위) |
| **트래픽 급증** | 오래된 데이터가 빠르게 밀려남 | 일정 시간 데이터 유지 |
| **낮은 트래픽** | 빠르게 메트릭 수집 | 데이터 수집 느림 |
| **평가 범위** | 트래픽 패턴에 따라 변동 | 항상 일정 (N초) |
| **오버헤드** | 낮음 | 약간 높음 |

### CountWindow를 선택하세요 {#choose-countwindow}

**적합한 경우:**

- 트래픽이 안정적이고 예측 가능
- 메모리 효율이 중요
- 빠른 메트릭 수집 필요

**예시:** 내부 마이크로서비스 간 통신, 배치 작업

### TimeWindow를 선택하세요 {#choose-timewindow}

**적합한 경우:**

- 트래픽 패턴이 불규칙
- 시간 기반 정책 필요
- 실시간 모니터링 중요

**예시:** 공개 API, 사용자 대면 서비스, 외부 서비스 호출

## 메트릭 계산 {#metrics}

두 window 타입 모두 동일한 메트릭을 제공합니다:

```python
from fluxgate.windows import CountWindow
from fluxgate.metric import Record

window = CountWindow(size=100)

# 호출 기록
window.record(Record(success=True, duration=0.5, timestamp=1234567890.0))
window.record(Record(success=False, duration=1.2, timestamp=1234567891.0))

# 메트릭 조회
metric = window.get_metric()
print(f"Total calls: {metric.total_count}")
print(f"Failed calls: {metric.failure_count}")
print(f"Average duration: {metric.avg_duration}")
```

**제공 메트릭:**

- `total_count` - 총 호출 수
- `failure_count` - 실패 호출 수
- `total_duration` - 총 응답 시간
- `slow_count` - 느린 호출 수
- `avg_duration` - 평균 응답 시간 (property)
- `failure_rate` - 실패율 (property)
- `slow_rate` - 느린 호출 비율 (property)

## 초기화 {#auto-reset}

Window는 circuit breaker의 상태가 변경될 때 초기화됩니다.

## 성능 고려사항 {#performance}

| 연산 | CountWindow | TimeWindow |
|-----|-------------|------------|
| **메모리** | O(N) - N개 기록 | O(N) - N개 버킷 (1초) |
| **record()** | O(1) | O(1) |
| **get_metric()** | O(1) | O(1) |

두 구현 모두 효율적이며 대부분의 프로덕션 환경에서 무시할 수 있는 오버헤드를 가집니다.

## 다음 단계 {#next-steps}

- [Trackers](trackers.md) - 어떤 예외를 추적할지 정의
- [Trippers](trippers.md) - Window 메트릭을 기반으로 circuit 제어
