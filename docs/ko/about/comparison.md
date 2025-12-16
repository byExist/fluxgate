# 다른 라이브러리와의 비교

이 페이지는 Fluxgate와 다른 인기 있는 Python Circuit Breaker 라이브러리를 공정하게 비교합니다. 목표는 다양한 설계 철학과 기능을 강조하여 특정 요구에 가장 적합한 도구를 선택하는 데 도움을 드리는 것입니다.

## 기능 비교

| 기능 | Fluxgate | circuitbreaker | pybreaker | aiobreaker |
|---|:---:|:---:|:---:|:---:|
| **비동기 지원** | ✅ | ✅ | (Tornado만) | ✅ |
| **주요 트립 로직** | 실패율, 연속 실패 | 연속 실패 | 연속 실패 | 연속 실패 |
| **슬라이딩 윈도우** | ✅ (카운트 또는 시간) | ❌ | ❌ | ❌ |
| **지연 기반 트립** | ✅ (`AvgLatency`, `SlowRate`) | ❌ | ❌ | ❌ |
| **조합 가능한 규칙 (&, \|)** | ✅ | ❌ | ❌ | ❌ |
| **점진적 복구** (`RampUp`)| ✅ | ❌ | ❌ | ❌ |
| **상태 Listener** | ✅ | ❌ | ✅ | ✅ |
| **내장 모니터링** | ✅ (Prometheus, Slack) | ❌ | ❌ | ❌ |
| **외부 상태 저장소** | ❌ | ❌ | ✅ (Redis) | ✅ (Redis) |

---

## 주요 차이점

### 1. 더 견고한 트립 로직

대부분의 라이브러리는 간단한 **연속 실패 횟수**를 기반으로 트립됩니다. 이는 깨지기 쉬울 수 있습니다. 서비스가 여전히 비정상 상태이더라도 단 한 번의 성공적인 호출로 카운터가 0으로 재설정될 수 있습니다.

Fluxgate는 **슬라이딩 윈도우를 통한 실패율**을 사용하며, 이는 서비스 상태를 훨씬 더 정확하고 안정적으로 평가할 수 있습니다. 또한 Fluxgate는 콜드 스타트 또는 서비스 완전 장애 시 빠른 보호를 위해 `FailureStreak`을 통한 연속 실패 감지도 지원합니다. 두 접근 방식을 결합하여 최대한의 회복력을 확보할 수 있습니다.

- **다른 라이브러리:**

    <!--pytest.mark.skip-->

    ```python
    # 5번 연속 실패 후 열립니다.
    @circuit(failure_threshold=5)
    def call_api(): ...
    ```

- **Fluxgate:**

    ```python
    from fluxgate import CircuitBreaker
    from fluxgate.trippers import MinRequests, FailureRate

    # 실패율이 50%를 초과하면 열립니다
    cb = CircuitBreaker(
        name="api",
        tripper=MinRequests(10) & FailureRate(0.5),
    )
    ```

### 2. 조합 가능하고 유연한 규칙

Fluxgate는 간단한 컴포넌트를 논리 연산자(`&`, `|`)와 결합하여 정교하고 세분화된 규칙을 구축할 수 있도록 합니다. 다른 라이브러리는 일반적으로 단일 조건만 지원합니다.

- **다른 라이브러리:** 단일 임계값.
- **Fluxgate:**

    ```python
    from fluxgate.trippers import Closed, HalfOpened, MinRequests, FailureRate, SlowRate

    # 다른 상태에 대해 다른 규칙을 사용합니다.
    tripper = (
        (Closed() & MinRequests(10) & FailureRate(0.5)) |
        (HalfOpened() & MinRequests(5) & FailureRate(0.3))
    )

    # 높은 실패율 또는 높은 느린 호출율에서 트립됩니다.
    tripper = MinRequests(10) & (FailureRate(0.5) | SlowRate(0.3))
    ```

### 3. 지연 기반 트립

Fluxgate는 예외뿐만 아니라 응답 시간을 기반으로 트립할 수 있습니다. 이는 서비스 "Brown-out"(서비스가 느리지만 실패하지는 않는 경우)을 감지하는 데 중요합니다.

- **다른 라이브러리:** 예외에만 반응할 수 있습니다.
- **Fluxgate:**

    ```python
    from fluxgate import CircuitBreaker
    from fluxgate.trippers import MinRequests, AvgLatency, SlowRate

    # 평균 지연 시간이 2초를 초과하면 트립됩니다.
    tripper = MinRequests(10) & AvgLatency(2.0)

    # 호출의 30% 이상이 1초보다 느리면 트립됩니다.
    cb = CircuitBreaker(
        name="api",
        tripper=MinRequests(10) & SlowRate(0.3),
        slow_threshold=1.0,  # "느림"의 기준을 정의합니다
    )
    ```

### 4. 점진적 복구

서비스가 복구 중일 때는 과부하를 피하기 위해 트래픽을 점진적으로 재도입해야 합니다. Fluxgate는 이를 위해 `RampUp`을 제공합니다. 다른 라이브러리는 일반적으로 한 번에 하나의 테스트 호출만 허용합니다.

- **다른 라이브러리:** 하나의 호출을 허용하고, 성공하면 회로를 닫습니다.
- **Fluxgate:**

    <!--pytest.mark.skip-->

    ```python
    from fluxgate.permits import RampUp

    # 60초 동안 트래픽을 10%에서 80%로 점진적으로 증가시킵니다.
    cb = CircuitBreaker(
        permit=RampUp(initial=0.1, final=0.8, duration=60.0),
        ...
    )
    ```

---

## 각 라이브러리를 선택하는 경우

### `Fluxgate`를 선택해야 하는 경우

가장 강력하고 기능이 풍부한 Circuit Breaker가 필요합니다.

- **실패율**, **지연 시간** 또는 **연속 실패** (`FailureStreak`)를 기반으로 트리거하고 싶습니다.
- **복잡하고 조합 가능한 규칙**(예: 다른 상태에 대한 다른 임계값)이 필요합니다.
- 복구 중에 트래픽을 **점진적으로 증가**시키고 싶습니다.
- 현대적인 **asyncio** 애플리케이션을 구축 중입니다.
- 더 나은 개발자 경험을 위해 완전히 **타입 힌트**된 API를 중요하게 생각합니다.

### `circuitbreaker`를 선택해야 하는 경우?

기본적인 사용 사례에 대한 간단하고 안정적이며 널리 사용되는 라이브러리가 필요합니다.

- **연속 실패** 기반의 트리거가 요구 사항을 충족합니다.
- 단순성과 최소한의 구성을 중요하게 생각합니다.

### `pybreaker` 또는 `aiobreaker`를 선택해야 하는 경우?

여러 프로세스나 서버 간에 **Circuit Breaker 상태를 공유**해야 하는 엄격한 요구 사항이 있습니다.

- 아키텍처에 분산 상태 저장소(Redis)가 필요합니다.
- `pybreaker`는 스레드 또는 Tornado 기반 애플리케이션에 적합합니다.
- `aiobreaker`는 `pybreaker`의 `asyncio` 버전입니다.

## 함께 보기

- [설계 및 영감](design.md): Fluxgate의 철학에 대해 알아보세요.
- [컴포넌트 개요](../components/index.md): 이러한 기능을 가능하게 하는 컴포넌트에 대해 자세히 알아보세요.
