# API 레퍼런스

소스 코드에서 자동 생성된 Fluxgate 공개 API 레퍼런스입니다.

- [Core](core.md) — `CircuitBreaker`, `AsyncCircuitBreaker`, 공통 타입
- [Windows](windows.md) — 호출 결과를 추적하는 슬라이딩 윈도우 전략
- [Trackers](trackers.md) — 어떤 결과를 실패로 간주할지 결정하는 조합 가능한 규칙
- [Trippers](trippers.md) — 회로를 `CLOSED`에서 `OPEN`으로 전환시키는 조건
- [Retries](retries.md) — `OPEN`에서 `HALF_OPEN`으로 전환하는 전략
- [Permits](permits.md) — `HALF_OPEN`에서 허용할 프로브 호출 수를 제어
- [Listeners](listeners.md) — 관찰 가능성 통합 (로깅, Prometheus, Slack)
- [Interfaces](interfaces.md) — 커스텀 컴포넌트 작성을 위한 프로토콜
