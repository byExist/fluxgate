from dataclasses import dataclass
from fluxgate.state import StateEnum


@dataclass(frozen=True, slots=True)
class Signal:
    circuit_name: str
    old_state: StateEnum
    new_state: StateEnum
    timestamp: float
