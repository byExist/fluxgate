"""Circuit breaker event listeners.

Available listeners:
    - LogListener: Logs state transitions (always available, works with sync/async)
    - PrometheusListener: Exports metrics to Prometheus (requires: pip install fluxgate[prometheus], works with sync/async)
    - SlackListener / AsyncSlackListener: Sends alerts to Slack (requires: pip install fluxgate[slack])

Usage:
    from fluxgate.listeners.log import LogListener
    from fluxgate.listeners.prometheus import PrometheusListener
    from fluxgate.listeners.slack import SlackListener, AsyncSlackListener
"""

from abc import ABC, abstractmethod

from fluxgate.signal import Signal

__all__ = ["Listener", "AsyncListener"]


class Listener(ABC):
    """Base class for synchronous circuit breaker listeners.

    Subclasses override ``__call__`` to react to state transitions.
    """

    @abstractmethod
    def __call__(self, signal: Signal) -> None: ...


class AsyncListener(ABC):
    """Base class for asynchronous circuit breaker listeners.

    Subclasses override ``__call__`` to react to state transitions.
    """

    @abstractmethod
    async def __call__(self, signal: Signal) -> None: ...
