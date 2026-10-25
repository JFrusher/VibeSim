import random

import pytest

from vibesim.core.engine import Engine
from vibesim.core.state import Anomaly, SimulationConfig
from vibesim.domains.logistics import VehiclePlugin, delivery_van

WINCHESTER = [(50.9097, -1.4043), (51.0632, -1.3080)]
PORTSMOUTH = [(50.9097, -1.4043), (50.8198, -1.0880)]


def fleet(*vans) -> Engine:
    return Engine(SimulationConfig(domain="logistics", entities=list(vans)))


def test_three_vans_move_toward_destination_over_10_ticks():
    engine = fleet(
        delivery_van("van-01", WINCHESTER, delay_p=0),
        delivery_van("van-02", WINCHESTER, delay_p=0),
        delivery_van("van-03", PORTSMOUTH, delay_p=0),
    )
    start = {k: dict(v) for k, v in engine.state.entities.items()}
    for _ in range(10):
        engine.step()
    for vid, s in engine.state.entities.items():
        dest = (PORTSMOUTH if vid == "van-03" else WINCHESTER)[-1]
        before = abs(start[vid]["lat"] - dest[0]) + abs(start[vid]["lon"] - dest[1])
        after = abs(s["lat"] - dest[0]) + abs(s["lon"] - dest[1])
        assert after < before
        assert s["odometer_km"] == pytest.approx(45 * 10 / 3600, abs=1e-4)
        assert s["battery_pct"] == pytest.approx(99.0)


def test_follows_multi_point_path_and_arrives():
    path = [(0.0, 0.0), (0.0, 0.001), (0.001, 0.001)]
    plugin = VehiclePlugin({"path": [list(p) for p in path], "speed_kmh": 3600})
    state = {"status": "en_route", "odometer_km": 0.0}
    plugin.init_state(state)
    plugin.tick(state, 0.1, random.Random(0))  # 0.1 km: past the first corner (~0.111 km)? no, just before
    assert state["lat"] == pytest.approx(0.0) and 0 < state["lon"] < 0.001
    plugin.tick(state, 0.1, random.Random(0))
    assert state["lon"] == pytest.approx(0.001) and state["lat"] > 0
    plugin.tick(state, 1.0, random.Random(0))
    assert (state["lat"], state["lon"], state["status"]) == (0.001, 0.001, "arrived")


def test_battery_runs_out_and_van_stops():
    engine = fleet(delivery_van("van-01", WINCHESTER, delay_p=0, drain_pct_per_s=30))
    events = [e for _ in range(5) for e in engine.step()]
    van = engine.state.entities["van-01"]
    assert van["battery_pct"] == 0.0 and van["status"] == "out_of_battery"
    stopped_at = van["odometer_km"]
    engine.step()
    assert engine.state.entities["van-01"]["odometer_km"] == stopped_at
    changes = [e.data for e in events if e.event_type == "state_changed"]
    assert changes == [{"field": "status", "from": "en_route", "to": "out_of_battery"}]


def test_traffic_delays_slow_the_van():
    slow = fleet(delivery_van("van-01", WINCHESTER, delay_p=1.0))
    fast = fleet(delivery_van("van-01", WINCHESTER, delay_p=0.0))
    for _ in range(5):
        slow.step()
        fast.step()
    assert slow.state.entities["van-01"]["status"] == "delayed"
    assert slow.state.entities["van-01"]["odometer_km"] < fast.state.entities["van-01"]["odometer_km"]


def test_chaos_override_reflected_immediately():
    engine = fleet(delivery_van("van-01", WINCHESTER), delivery_van("van-02", WINCHESTER))
    engine.step()
    engine.inject(Anomaly(name="dead-battery", targets=["van-01"], set={"battery_pct": 0}))
    events = {(e.entity_id, e.event_type): e for e in engine.step()}
    van1 = events[("van-01", "telemetry_update")]
    assert van1.data["battery_pct"] == 0.0
    assert van1.data["status"] == "out_of_battery"
    assert van1.anomalies_applied == ["dead-battery"]
    assert ("van-01", "state_changed") in events
    assert events[("van-02", "telemetry_update")].anomalies_applied == []


def test_bad_path_rejected_at_creation():
    with pytest.raises(ValueError, match="path"):
        fleet(delivery_van("van-01", [(50.9, -1.4)]))
