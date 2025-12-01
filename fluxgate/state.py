from enum import Enum


class StateEnum(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    METRICS_ONLY = "metrics_only"
    DISABLED = "disabled"
    FORCED_OPEN = "forced_open"
