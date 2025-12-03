# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2024-XX-XX

This is the initial public release of Fluxgate.

### Features

- ✨ **Core**: Initial implementation of `CircuitBreaker` and `AsyncCircuitBreaker`.
- ✨ **Windows**: Sliding window strategies (`CountWindow`, `TimeWindow`).
- ✨ **Trackers**: Composable failure trackers (`All`, `TypeOf`, `Custom`) with `&`, `|`, and `~` operators.
- ✨ **Trippers**: Composable tripping conditions (`Closed`, `HalfOpened`, `MinRequests`, `FailureRate`, `AvgLatency`, `SlowRate`) with `&` and `|` operators.
- ✨ **Retries**: Recovery strategies (`Never`, `Always`, `Cooldown`, `Backoff`).
- ✨ **Permits**: Gradual recovery strategies (`Random`, `RampUp`).
- ✨ **Listeners**: Built-in monitoring and alerting integrations (`LogListener`, `PrometheusListener`, `SlackListener`).
- ✨ **Manual Control**: Methods for manual intervention (`disable`, `metrics_only`, `force_open`, `reset`).
- ✨ **Typing**: Full type hinting and `py.typed` compliance for excellent IDE support.
