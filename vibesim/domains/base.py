"""Plugin interface for physics the declarative fields can't express."""

import random
from abc import ABC, abstractmethod
from typing import Any


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class Plugin(ABC):
    """One instance per entity. Validate and precompute in __init__; raise ValueError on bad params."""

    @abstractmethod
    def __init__(self, params: dict[str, Any]): ...

    @abstractmethod
    def init_state(self, state: dict[str, Any]) -> None:
        """Fill in any state fields the plugin owns that the config left out."""

    @abstractmethod
    def tick(self, state: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        """Advance `state` in place by `dt_s` simulated seconds."""

    def clamp(self, state: dict[str, Any]) -> None:  # noqa: B027 - optional hook
        """Keep plugin-owned fields inside physical bounds."""
