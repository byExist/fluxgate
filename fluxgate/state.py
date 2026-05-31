from typing import Literal

__all__ = ["State"]


State = Literal[
    "closed",
    "open",
    "half_open",
    "metrics_only",
    "disabled",
    "forced_open",
]
