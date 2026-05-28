from dataclasses import dataclass
from fluxgate.state import StateEnum


@dataclass(frozen=True, slots=True)
class Signal:
    old_state: StateEnum
    new_state: StateEnum
    timestamp: float
