import random

import pytest

from src.core.engine import Engine
from src.core.state import Anomaly, EntityConfig, SimulationConfig
from src.domains.logistics import ROUTES, LogisticsDomain


def van(i: int, route: str = "southampton_to_winchester", **rules) -> EntityConfig:
    lat, lon = ROUTES[route][0]
    return EntityConfig(id=f"van-{i:02d}", type="delivery_vehicle",
                        initial_state={"lat": lat, "lon": lon, "battery_pct": 98.5, "status": "en_route"},
                        behavior_rules={"speed_kmh": 45, "battery_drain_rate": 0.1, "route": route,
                                        "traffic_delay_prob": 0.0, **rules})


def test_three_vans_move_toward_destination_over_10_ticks():
    engine = Engine(SimulationConfig(domain="logistics", entities=[van(1), van(2), van(3, "southampton_to_portsmouth")]))
    start = {k: dict(v) for k, v in engine.state.entities.items()}
    for _ in range(10):
        engine.step()
    for vid, s in engine.state.entities.items():
        dest = ROUTES["southampton_to_portsmouth" if vid == "van-03" else "southampton_to_winchester"][1]
        before = abs(start[vid]["lat"] - dest[0]) + abs(start[vid]["lon"] - dest[1])
        after = abs(s["lat"] - dest[0]) + abs(s["lon"] - dest[1])
        assert after < before
        assert s["battery_pct"] == pytest.approx(97.5)


def test_arrives_and_stops_at_destination():
    state = {"lat": 51.0631, "lon": -1.3080, "battery_pct": 50.0, "status": "en_route"}
    LogisticsDomain().tick(state, van(1).behavior_rules, 1.0, random.Random(0))
    assert (state["lat"], state["lon"], state["status"]) == (*ROUTES["southampton_to_winchester"][1], "arrived")


def test_battery_clamps_at_zero_and_van_stops():
    state = {"lat": 50.9097, "lon": -1.4043, "battery_pct": 0.05, "status": "en_route"}
    LogisticsDomain().tick(state, van(1).behavior_rules, 1.0, random.Random(0))
    assert state["battery_pct"] == 0.0
    assert state["status"] == "out_of_battery"


def test_traffic_delays_slow_the_van():
    rng = random.Random(0)
    domain = LogisticsDomain()
    state = dict(van(1).initial_state)
    domain.tick(state, {**van(1).behavior_rules, "traffic_delay_prob": 1.0}, 1.0, rng)
    assert state["status"] == "delayed"


def test_chaos_override_reflected_immediately():
    engine = Engine(SimulationConfig(domain="logistics", entities=[van(1), van(2)]))
    engine.step()
    engine.inject(Anomaly(name="dead-battery", entity_id="van-01", set={"battery_pct": 0}))
    events = {e.entity_id: e for e in engine.step()}
    assert events["van-01"].data["battery_pct"] == 0.0
    assert events["van-01"].data["status"] == "out_of_battery"
    assert events["van-01"].anomalies_applied == ["dead-battery"]
    assert events["van-02"].data["battery_pct"] > 0
    assert events["van-02"].anomalies_applied == []


def test_unknown_route_rejected_at_creation():
    with pytest.raises(ValueError, match="unknown route"):
        Engine(SimulationConfig(domain="logistics", entities=[van(1, route="southampton_to_winchester")
                                                               .model_copy(update={"behavior_rules": {"speed_kmh": 1, "battery_drain_rate": 0.1, "route": "nowhere"}})]))
