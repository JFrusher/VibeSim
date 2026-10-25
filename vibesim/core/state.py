"""Data models and the in-memory state graph for one simulation."""

import copy
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = None
    max: float | None = None
    noise: float = Field(0.0, ge=0.0)  # gaussian sd, scaled by sqrt(dt)
    when: str | None = None  # expression; the field only updates while true
    round: int | None = None


class Drift(FieldBase):
    behavior: Literal["drift"]
    rate: float = 0.0  # units per second; rate 0 + noise is a random walk


class MeanRevert(FieldBase):
    behavior: Literal["mean_revert"]
    target: float
    strength: float = Field(0.1, ge=0.0)  # fraction of the gap closed per second


class Cycle(FieldBase):
    behavior: Literal["cycle"]
    base: float
    amplitude: float
    period_s: float = Field(gt=0.0)
    phase_s: float = 0.0


class Derived(FieldBase):
    behavior: Literal["derived"]
    expr: str


FieldSpec = Annotated[Drift | MeanRevert | Cycle | Derived, Field(discriminator="behavior")]


class Transition(BaseModel):
    """Moves `status` from `source` to `target` when `when` holds, with probability `p` per second."""

    model_config = ConfigDict(extra="forbid")

    source: str | list[str]  # "*" matches any status
    target: str
    p: float | None = Field(None, ge=0.0, le=1.0)
    when: str | None = None

    @model_validator(mode="after")
    def has_trigger(self) -> Self:
        if self.p is None and self.when is None:
            raise ValueError("transition needs 'p', 'when', or both")
        return self


class PluginRef(BaseModel):
    name: str
    params: dict[str, Any] = {}


class EntityConfig(BaseModel):
    """One entity, or `count` identical ones with ids `{id}-01`, `{id}-02`, ..."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    count: int = Field(1, ge=1)
    initial_state: dict[str, Any] = {}
    fields: dict[str, FieldSpec] = {}  # evaluated in order, so later fields can read earlier ones
    machine: list[Transition] = []  # drives the `status` field; first matching transition wins
    plugin: PluginRef | None = None

    def instance_ids(self) -> list[str]:
        return [self.id] if self.count == 1 else [f"{self.id}-{i:02d}" for i in range(1, self.count + 1)]


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
    domain: str  # free-text label, e.g. "logistics"
    tick_interval_ms: int = Field(1000, ge=100)
    seed: int = 0
    entities: list[EntityConfig] = Field(min_length=1)
    chaos_rules: ChaosRules = ChaosRules()


class TelemetryEvent(BaseModel):
    timestamp: datetime
    tick: int
    entity_id: str
    event_type: Literal["telemetry_update", "state_changed"] = "telemetry_update"
    data: dict[str, Any]
    anomalies_applied: list[str] = []


class SimulationState:
    """Current tick and per-entity state.

    Mutated only from the engine's event loop, so no lock is needed.
    """

    def __init__(self, initial: dict[str, dict[str, Any]]):
        self.tick = 0
        self.entities = copy.deepcopy(initial)

    def snapshot(self) -> dict[str, Any]:
        return {"tick": self.tick, "entities": copy.deepcopy(self.entities)}


def utcnow() -> datetime:
    return datetime.now(UTC)
