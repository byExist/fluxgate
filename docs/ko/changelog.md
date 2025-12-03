# 변경 기록

이 프로젝트의 모든 변경 사항은 이 파일에 문서화됩니다.

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
