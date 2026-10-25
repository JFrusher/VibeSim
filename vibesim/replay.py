"""Replays a recording through the normal transports, event for event."""

import json
import uuid
from collections import defaultdict

from vibesim import storage
from vibesim.core.engine import Engine
from vibesim.core.state import Anomaly, ChaosRules, Persistence, SimulationConfig, TelemetryEvent


class ReplayEngine(Engine):
    def __init__(self, recording_id: str, speed: float = 1.0):
        if speed <= 0:
            raise ValueError("replay speed must be above 0")
        path = storage.recording_path(recording_id)
        if recording_id not in storage.list_recordings():
            raise ValueError(f"no recording '{recording_id}'; known: {storage.list_recordings()}")
        header, *lines = path.read_text().splitlines()
        recorded = SimulationConfig.model_validate_json(header)
        super().__init__(
            recorded.model_copy(
                update={
                    "simulation_id": f"replay-{uuid.uuid4().hex[:12]}",
                    "chaos_rules": ChaosRules(),  # chaos is already baked into the recorded events
                    "persistence": Persistence(),
                }
            )
        )
        self.recording_id = recording_id
        self.speed = speed
        self._events: dict[int, list[TelemetryEvent]] = defaultdict(list)
        for line in lines:
            record = json.loads(line)
            self._events[record["emitted_at"]].append(TelemetryEvent.model_validate(record["event"]))
        self.last_tick = max(self._events, default=0)

    @property
    def interval_s(self) -> float:
        return super().interval_s / self.speed

    def step(self, publish: bool = True) -> list[TelemetryEvent]:
        if self.status in ("stopped", "failed"):
            raise RuntimeError(f"simulation is {self.status}")
        tick = self.state.tick + 1
        if tick > self.last_tick:
            self.stop()  # end of recording: closes every stream
            return []
        events = self._events.get(tick, [])
        for event in events:
            if event.event_type == "telemetry_update":
                self.state.entities[event.entity_id] = dict(event.data)
        self.state.tick = tick
        if publish:
            for event in events:
                self._publish(event)
        return events

    def inject(self, anomaly: Anomaly) -> None:
        raise ValueError("replays are read-only; chaos was recorded with the original run")
