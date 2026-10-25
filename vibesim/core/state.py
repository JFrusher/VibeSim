"""Data models and the in-memory state graph for one simulation."""

import copy
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Domain = Literal["logistics", "devops"]


class EntityConfig(BaseModel):
    id: str
    type: str
    initial_state: dict[str, Any]
    behavior_rules: dict[str, Any] = {}


class Anomaly(BaseModel):
    name: str
    entity_id: str | None = None  # None targets every entity
    set: dict[str, Any] = {}  # state fields forced while the anomaly is active
    drop_rate: float = Field(0.0, ge=0.0, le=1.0)  # fraction of events not emitted
    duration_ticks: int | None = Field(None, ge=1)  # None lasts until removed


class ChaosRules(BaseModel):
    active_anomalies: list[Anomaly] = []


class SimulationConfig(BaseModel):
    schema_version: Literal[1] = 1
    simulation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: Domain
    tick_interval_ms: int = Field(1000, ge=100)
    seed: int = 0
    entities: list[EntityConfig] = Field(min_length=1)
    chaos_rules: ChaosRules = ChaosRules()


class TelemetryEvent(BaseModel):
    timestamp: datetime
    tick: int
    entity_id: str
    event_type: str = "telemetry_update"
    data: dict[str, Any]
    anomalies_applied: list[str] = []


class SimulationState:
    """Current tick and per-entity state.

    Mutated only from the engine's event loop, so no lock is needed.
    """

    def __init__(self, config: SimulationConfig):
        self.tick = 0
        self.entities: dict[str, dict[str, Any]] = {e.id: copy.deepcopy(e.initial_state) for e in config.entities}

    def snapshot(self) -> dict[str, Any]:
        return {"tick": self.tick, "entities": copy.deepcopy(self.entities)}


def utcnow() -> datetime:
    return datetime.now(UTC)
