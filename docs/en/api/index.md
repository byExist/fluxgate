# API Reference

Complete reference for Fluxgate's public API, generated from source.

- [Core](core.md) — `CircuitBreaker`, `AsyncCircuitBreaker`, and shared types
- [Windows](windows.md) — sliding-window strategies for tracking call outcomes
- [Trackers](trackers.md) — composable rules for deciding what counts as a failure
- [Trippers](trippers.md) — conditions that move the circuit from `CLOSED` to `OPEN`
- [Retries](retries.md) — strategies for transitioning from `OPEN` to `HALF_OPEN`
- [Permits](permits.md) — controls for how many probe calls are allowed in `HALF_OPEN`
- [Listeners](listeners.md) — observability integrations (logging, Prometheus, Slack)
- [Interfaces](interfaces.md) — protocols for writing custom components
