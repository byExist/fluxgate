# Changelog

All notable changes to this project will be documented in this file.

## [0.1.2] - 2025.12.03

### Changed

- **LogListener**: Added `logger` and `level_map` parameters for flexible logging configuration.
    - `logger`: Inject a custom logger instance instead of using the root logger.
    - `level_map`: Customize log levels per state (default: `OPEN`/`FORCED_OPEN` → `WARNING`, others → `INFO`).

## [0.1.1] - 2025.12.01

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
