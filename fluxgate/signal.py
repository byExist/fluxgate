from dataclasses import dataclass
from fluxgate.state import State


@dataclass(frozen=True, slots=True)
class Signal:
    old_state: State
    new_state: State
    timestamp: float
