# Release Notes

## 0.1.1

Initial release.

### Features

- ✨ Add `CircuitBreaker` and `AsyncCircuitBreaker` for sync and async support.
- ✨ Add sliding windows: `CountWindow` (count-based) and `TimeWindow` (time-based).
- ✨ Add composable trackers with `&`, `|`, `~` operators: `All`, `TypeOf`, `Custom`.
- ✨ Add composable trippers with `&`, `|` operators: `Closed`, `HalfOpened`, `MinRequests`, `FailureRate`, `AvgLatency`, `SlowRate`.
- ✨ Add retry strategies: `Never`, `Always`, `Cooldown`, `Backoff`.
- ✨ Add permit strategies: `Random`, `RampUp`.
- ✨ Add listeners for monitoring: `LogListener`, `PrometheusListener`, `SlackListener`.
- ✨ Add manual control methods: `disable()`, `enable()`, `force_open()`, `reset()`.
- ✨ Full type hints with `py.typed` marker.
