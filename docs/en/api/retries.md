# API: Retries

This page documents the available recovery retry strategies. Retry strategies determine when the circuit breaker should attempt to recover by moving from the `OPEN` state to the `HALF_OPEN` state.

For a high-level guide on choosing a retry strategy, see the [Retries Component Guide](../components/retries.md).

---

::: fluxgate.retries.Always

::: fluxgate.retries.Never

::: fluxgate.retries.Cooldown

::: fluxgate.retries.Backoff
