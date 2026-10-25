"""Runtime anomalies: forced (optionally ramped) overrides, dropped and delayed events,
scheduled timelines and random incidents."""

import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from vibesim.core.state import Anomaly, ChaosRules


@dataclass
class _Active:
    anomaly: Anomaly
    injected_at: int
    # ramp start values, captured per entity the first time the anomaly touches it
    ramp_from: dict[tuple[str, str], float] = field(default_factory=dict)

    @property
    def expires_at(self) -> int | None:
        d = self.anomaly.duration_ticks
        return None if d is None else self.injected_at + d


class ChaosInjector:
    def __init__(self, rules: ChaosRules, entity_ids: Iterable[str]):
        self.entity_ids = set(entity_ids)
        self.rules = rules
        self._active: dict[str, _Active] = {}
        self._random_count = 0
        for anomaly in rules.active_anomalies:
            self.inject(anomaly, 0)
        for step in rules.timeline:
            if step.inject:
                self._check_targets(step.inject)
        for anomaly in rules.random.catalogue if rules.random else []:
            self._check_targets(anomaly)

    @property
    def anomalies(self) -> list[Anomaly]:
        return [a.anomaly for a in self._active.values()]

    def inject(self, anomaly: Anomaly, current_tick: int) -> None:
        if anomaly.name in self._active:
            raise ValueError(f"anomaly '{anomaly.name}' is already active")
        self._check_targets(anomaly)
        self._active[anomaly.name] = _Active(anomaly, current_tick)

    def remove(self, name: str) -> None:
        if name not in self._active:
            raise KeyError(name)
        del self._active[name]

    def begin_tick(self, tick: int, dt_s: float, rng: random.Random) -> None:
        """Expire finished anomalies, run timeline steps due now, maybe start a random incident."""
        for name, active in list(self._active.items()):
            if active.expires_at is not None and tick > active.expires_at:
                del self._active[name]
        for step in self.rules.timeline:
            if step.at_tick != tick:
                continue
            if step.inject:
                self.inject(step.inject, tick - 1)
            elif step.remove in self._active:
                del self._active[step.remove]
        chaos = self.rules.random
        if chaos and rng.random() < chaos.per_minute * dt_s / 60:
            self._random_count += 1
            incident = rng.choice(chaos.catalogue)
            self.inject(incident.model_copy(update={"name": f"{incident.name}#{self._random_count}"}), tick - 1)

    def for_entity(self, entity_id: str) -> list[Anomaly]:
        return [a.anomaly for a in self._active.values() if a.anomaly.targets is None or entity_id in a.anomaly.targets]

    def overrides(self, entity_id: str, state: dict[str, Any], tick: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for active in self._active.values():
            a = active.anomaly
            if a.targets is not None and entity_id not in a.targets:
                continue
            for key, target in a.set.items():
                if a.ramp_ticks and isinstance(target, int | float) and isinstance(state.get(key), int | float):
                    start = active.ramp_from.setdefault((entity_id, key), float(state[key]))
                    progress = min(1.0, (tick - active.injected_at) / a.ramp_ticks)
                    result[key] = start + (target - start) * progress
                else:
                    result[key] = target
        return result

    @staticmethod
    def should_drop(anomalies: list[Anomaly], rng: random.Random) -> bool:
        return any(rng.random() < a.drop_rate for a in anomalies)

    @staticmethod
    def delay(anomalies: list[Anomaly], rng: random.Random) -> int:
        return max((a.delay_ticks + rng.randint(0, a.jitter_ticks) for a in anomalies), default=0)

    def _check_targets(self, anomaly: Anomaly) -> None:
        if anomaly.targets is not None and (unknown := set(anomaly.targets) - self.entity_ids):
            raise ValueError(f"anomaly '{anomaly.name}' targets unknown entities {sorted(unknown)}")
