from __future__ import annotations

import sys
from typing import Protocol

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from fluxgate.metric import Metric, Record
from fluxgate.signal import Signal
from fluxgate.state import StateEnum


class IWindow(Protocol):
    def record(self, record: Record) -> None: ...

    def get_metric(self) -> Metric: ...

    def reset(self) -> None: ...


class ITracker(Protocol):
    def __call__(self, exception: Exception) -> bool: ...

    def __and__(self, other: Self) -> ITracker: ...

    def __or__(self, other: Self) -> ITracker: ...

    def __invert__(self) -> ITracker: ...


class ITripper(Protocol):
    def __call__(
        self, metric: Metric, state: StateEnum, consecutive_failures: int
    ) -> bool: ...

    def __and__(self, other: Self) -> ITripper: ...

    def __or__(self, other: Self) -> ITripper: ...


class IRetry(Protocol):
    def __call__(self, changed_at: float, reopens: int) -> bool: ...


class IPermit(Protocol):
    def __call__(self, changed_at: float) -> bool: ...


class IListener(Protocol):
    def __call__(self, signal: Signal) -> None: ...


class IAsyncListener(Protocol):
    async def __call__(self, signal: Signal) -> None: ...
