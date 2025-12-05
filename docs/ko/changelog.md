# 변경 기록

이 프로젝트의 모든 변경 사항은 이 파일에 문서화됩니다.

## [0.3.0] - 2025.12.05

### Breaking Changes

- **`ITripper` 인터페이스 시그니처 변경**: `__call__` 메서드가 이제 선택적 `consecutive_failures` 파라미터를 받습니다. 커스텀 tripper 구현체는 시그니처를 업데이트해야 합니다:

```python
# 이전 (v0.2.x)
def __call__(self, metric: Metric, state: StateEnum) -> bool: ...

# 이후 (v0.3.0)
def __call__(self, metric: Metric, state: StateEnum, consecutive_failures: int = 0) -> bool: ...
```

### 추가

- **`FailureStreak` tripper**: N회 연속 실패 후 회로를 트립합니다. 콜드 스타트 또는 서비스 완전 장애 시 빠른 장애 감지에 유용합니다.

```python
from fluxgate.trippers import FailureStreak, MinRequests, FailureRate

# 5회 연속 실패 시 빠른 트립, 또는 50% 실패율 시 통계적 트립
tripper = FailureStreak(5) | (MinRequests(20) & FailureRate(0.5))
```

## [0.2.0] - 2025.12.03

### Breaking Changes

- **`slow_threshold` 필수화**: `slow_threshold` 파라미터가 더 이상 기본값을 갖지 않으며, `CircuitBreaker` 또는 `AsyncCircuitBreaker` 인스턴스 생성 시 명시적으로 설정해야 합니다.
    - `SlowRate`를 사용하지 않는 경우 `float("inf")`로 설정하여 느린 호출 추적을 비활성화하세요.
    - Python의 원칙을 따릅니다: "Explicit is better than implicit."

**마이그레이션:**

<!--pytest.mark.skip-->

```python
# 이전 (v0.1.x)
cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    ...
)

# 이후 (v0.2.0)
cb = CircuitBreaker(
    name="api",
    window=CountWindow(size=100),
    ...
    slow_threshold=float("inf"),  # 또는 3.0과 같은 특정 값
)
```

## [0.1.2] - 2025.12.03

### 변경

- **LogListener**: 유연한 로깅 설정을 위한 `logger` 및 `level_map` 파라미터 추가.
    - `logger`: 루트 logger 대신 커스텀 logger 인스턴스 주입 가능.
    - `level_map`: 상태별 로그 레벨 커스터마이징 (기본값: `OPEN`/`FORCED_OPEN` → `WARNING`, 나머지 → `INFO`).

## [0.1.1] - 2025.12.01

Fluxgate의 초기 공개 릴리스입니다.

### 기능

- ✨ **핵심**: `CircuitBreaker` 및 `AsyncCircuitBreaker`의 초기 구현.
- ✨ **Window**: 슬라이딩 윈도우 (`CountWindow`, `TimeWindow`).
- ✨ **Tracker**: `&`, `|`, `~` 연산자를 사용한 조합 가능한 실패 Tracker (`All`, `TypeOf`, `Custom`).
- ✨ **Tripper**: `&` 및 `|` 연산자를 사용한 조합 가능한 트립 조건 (`Closed`, `HalfOpened`, `MinRequests`, `FailureRate`, `AvgLatency`, `SlowRate`).
- ✨ **Retry**: 복구 (`Never`, `Always`, `Cooldown`, `Backoff`).
- ✨ **Permit**: 점진적 복구 (`Random`, `RampUp`).
- ✨ **Listener**: 내장 모니터링 및 알림 통합 (`LogListener`, `PrometheusListener`, `SlackListener`).
- ✨ **수동 제어**: 수동 개입을 위한 메서드 (`disable`, `metrics_only`, `force_open`, `reset`).
- ✨ **타이핑**: 뛰어난 IDE 지원을 위한 전체 타입 힌트 및 `py.typed` 준수.
