import random

import pytest

from vibesim.core.engine import Engine
from vibesim.core.entity import EntityRuntime
from vibesim.core.state import EntityConfig, SimulationConfig


def entity(**kw) -> EntityConfig:
    return EntityConfig.model_validate({"id": "e", "type": "thing", **kw})


def run(config: EntityConfig, ticks: int, dt_s: float = 1.0, seed: int = 0) -> dict:
    rt = EntityRuntime(config)
    state = rt.initial_state()
    rng = random.Random(seed)
    for tick in range(1, ticks + 1):
        rt.tick(state, tick, dt_s, rng)
    return state


def test_drift_is_per_second_and_clamped():
    e = entity(initial_state={"x": 5.0}, fields={"x": {"behavior": "drift", "rate": -1, "min": 0}})
    assert run(e, 3)["x"] == 2.0
    assert run(e, 3, dt_s=0.5)["x"] == 3.5
    assert run(e, 10)["x"] == 0.0


def test_mean_revert_converges():
    e = entity(initial_state={"x": 100.0}, fields={"x": {"behavior": "mean_revert", "target": 10, "strength": 0.5}})
    assert run(e, 30)["x"] == pytest.approx(10, abs=0.01)


def test_cycle_follows_sine():
    e = entity(fields={"x": {"behavior": "cycle", "base": 20, "amplitude": 5, "period_s": 4}})
    assert run(e, 1)["x"] == pytest.approx(25)
    assert run(e, 3)["x"] == pytest.approx(15)


def test_derived_reads_earlier_fields_and_time():
    e = entity(
        initial_state={"a": 1.0},
        fields={"a": {"behavior": "drift", "rate": 1}, "b": {"behavior": "derived", "expr": "a * 10 + t"}},
    )
    assert run(e, 2)["b"] == 32.0


def test_when_guard_freezes_field():
    e = entity(
        initial_state={"x": 0.0, "status": "off"},
        fields={"x": {"behavior": "drift", "rate": 1, "when": "status == 'on'"}},
    )
    assert run(e, 5)["x"] == 0.0


def test_machine_guards_probabilities_and_wildcards():
    e = entity(
        initial_state={"temp": 0.0, "status": "idle"},
        fields={"temp": {"behavior": "drift", "rate": 10}},
        machine=[
            {"source": "*", "target": "melted", "when": "temp >= 100"},
            {"source": "idle", "target": "busy", "p": 1.0},
            {"source": "busy", "target": "idle", "p": 0.0},
        ],
    )
    assert run(e, 1)["status"] == "busy"
    assert run(e, 10)["status"] == "melted"


def test_round():
    e = entity(initial_state={"x": 0.0}, fields={"x": {"behavior": "drift", "rate": 0.123456, "round": 2}})
    assert run(e, 1)["x"] == 0.12


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"fields": {"x": {"behavior": "derived", "expr": "nope + 1"}}}, "unknown names"),
        ({"initial_state": {"t": 1}}, "reserved"),
        ({"plugin": {"name": "teleporter"}}, "unknown plugin"),
        ({"machine": [{"source": "a", "target": "b", "p": 1}]}, "needs an initial 'status'"),
    ],
)
def test_invalid_configs_fail_fast(kw, message):
    with pytest.raises(ValueError, match=message):
        EntityRuntime(entity(**kw))


def test_transition_needs_a_trigger():
    with pytest.raises(ValueError, match="needs 'p', 'when'"):
        entity(initial_state={"status": "a"}, machine=[{"source": "a", "target": "b"}])


def test_count_expands_ids_and_duplicates_fail():
    many = entity(count=3, initial_state={"x": 0.0})
    assert list(Engine(SimulationConfig(domain="x", entities=[many])).state.entities) == ["e-01", "e-02", "e-03"]
    with pytest.raises(ValueError, match="duplicate"):
        Engine(SimulationConfig(domain="x", entities=[entity(), entity()]))


def test_pure_json_domain_runs():
    """A whole domain from config alone, no Python: a thermostat-driven room."""
    config = SimulationConfig.model_validate(
        {
            "domain": "smart_building",
            "entities": [
                {
                    "id": "room",
                    "type": "room",
                    "count": 2,
                    "initial_state": {"temp_c": 24.0, "status": "cooling"},
                    "fields": {
                        "temp_c": {"behavior": "drift", "rate": -0.5, "when": "status == 'cooling'", "round": 1},
                        "power_kw": {"behavior": "derived", "expr": "3.5 if status == 'cooling' else 0.1"},
                    },
                    "machine": [{"source": "cooling", "target": "idle", "when": "temp_c <= 21"}],
                }
            ],
        }
    )
    engine = Engine(config)
    for _ in range(10):
        events = engine.step()
    assert engine.state.entities["room-01"] == {"temp_c": 21.0, "status": "idle", "power_kw": 0.1}
    assert all(e.event_type == "telemetry_update" for e in events)
