"""Domain interface: how one entity's state advances per tick."""

import random
from abc import ABC, abstractmethod
from typing import Any


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class DomainModel(ABC):
    required_state: tuple[str, ...]
    required_rules: tuple[str, ...] = ()

    def validate(self, entity_id: str, state: dict[str, Any], rules: dict[str, Any]) -> None:
        """Reject configs that would crash mid-simulation."""
        missing = [k for k in self.required_state if k not in state] + [k for k in self.required_rules if k not in rules]
        if missing:
            raise ValueError(f"entity '{entity_id}' is missing {missing}")

    @abstractmethod
    def tick(self, state: dict[str, Any], rules: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        """Advance `state` in place by `dt_s` simulated seconds."""

    def apply_chaos(self, state: dict[str, Any], overrides: dict[str, Any]) -> None:
        """Force anomaly overrides onto `state`, then re-clamp to physical bounds."""
        state.update(overrides)
        self.clamp(state)

    @abstractmethod
    def clamp(self, state: dict[str, Any]) -> None:
        """Keep every numeric field inside realistic physical bounds."""
