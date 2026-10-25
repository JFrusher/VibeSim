"""Runtime anomaly injection: forced state overrides and dropped events."""

import random

from src.core.state import Anomaly


class ChaosInjector:
    def __init__(self, anomalies: list[Anomaly]):
        self.anomalies: list[Anomaly] = list(anomalies)
        self._expires_at: dict[str, int | None] = {a.name: None for a in self.anomalies}

    def inject(self, anomaly: Anomaly, current_tick: int) -> None:
        if anomaly.name in self._expires_at:
            raise ValueError(f"anomaly '{anomaly.name}' is already active")
        self.anomalies.append(anomaly)
        self._expires_at[anomaly.name] = (
            None if anomaly.duration_ticks is None else current_tick + anomaly.duration_ticks
        )

    def remove(self, name: str) -> None:
        if name not in self._expires_at:
            raise KeyError(name)
        del self._expires_at[name]
        self.anomalies = [a for a in self.anomalies if a.name != name]

    def expire(self, tick: int) -> None:
        for name, expires_at in list(self._expires_at.items()):
            if expires_at is not None and tick > expires_at:
                self.remove(name)

    def for_entity(self, entity_id: str) -> list[Anomaly]:
        return [a for a in self.anomalies if a.entity_id in (None, entity_id)]

    @staticmethod
    def should_drop(anomalies: list[Anomaly], rng: random.Random) -> bool:
        return any(rng.random() < a.drop_rate for a in anomalies)
