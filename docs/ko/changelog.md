# 릴리스 노트

## 0.1.0

최초 릴리스.

### Features

- ✨ 동기/비동기 지원을 위한 `CircuitBreaker`, `AsyncCircuitBreaker` 추가.
- ✨ 슬라이딩 윈도우 추가: `CountWindow` (개수 기반), `TimeWindow` (시간 기반).
- ✨ `&`, `|`, `~` 연산자로 조합 가능한 트래커 추가: `All`, `TypeOf`, `Custom`.
- ✨ `&`, `|` 연산자로 조합 가능한 트리퍼 추가: `Closed`, `HalfOpened`, `MinRequests`, `FailureRate`, `AvgLatency`, `SlowRate`.
- ✨ 재시도 전략 추가: `Never`, `Always`, `Cooldown`, `Backoff`.
- ✨ 허용 전략 추가: `Random`, `RampUp`.
- ✨ 모니터링을 위한 리스너 추가: `LogListener`, `PrometheusListener`, `SlackListener`.
- ✨ 수동 제어 메서드 추가: `disable()`, `enable()`, `force_open()`, `reset()`.
- ✨ `py.typed` 마커와 함께 완전한 타입 힌트 지원.
