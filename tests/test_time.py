from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from vibesim import storage
from vibesim.core.engine import Engine, simulations
from vibesim.core.state import (
    Anomaly,
    ChaosRules,
    EntityConfig,
    Persistence,
    RandomChaos,
    SimulationConfig,
)
from vibesim.domains.devops import microservice
from vibesim.replay import ReplayEngine
from vibesim.scenario import dump_scenario, load_scenario
from vibesim.transport.rest import app

START = datetime(2026, 1, 1, tzinfo=UTC)


def chaotic(**kw) -> SimulationConfig:
    """Noise, a status machine, random incidents with jitter: everything that consumes randomness."""
    catalogue = [
        Anomaly(name="lag", jitter_ticks=3, duration_ticks=4),
        Anomaly(name="hot", set={"cpu_pct": 99}, ramp_ticks=3, duration_ticks=5),
    ]
    return SimulationConfig(
        domain="devops",
        start_time=START,
        entities=[microservice("svc", count=3, memory_leak_pct_per_s=0.5)],
        chaos_rules=ChaosRules(random=RandomChaos(per_minute=20, catalogue=catalogue)),
        **kw,
    )


def dumps(events):
    return [e.model_dump_json() for e in events]


def test_time_scale_compresses_cycles_and_drives_timestamps():
    day = EntityConfig.model_validate(
        {
            "id": "sun",
            "type": "sky",
            "fields": {"light": {"behavior": "cycle", "base": 0, "amplitude": 1, "period_s": 86400}},
        }
    )
    engine = Engine(SimulationConfig(domain="x", start_time=START, time_scale=21600, entities=[day]))
    (event,) = engine.step()  # one tick = 6 simulated hours = a quarter day
    assert event.data["light"] == pytest.approx(1.0)
    assert event.timestamp == START + timedelta(hours=6)


def test_start_time_defaults_to_creation_and_is_pinned_in_config():
    engine = Engine(SimulationConfig(domain="x", entities=[microservice("s")]))
    assert engine.config.start_time is not None


def test_restored_snapshot_continues_identically():
    original = Engine(chaotic())
    for _ in range(60):
        original.step()
    assert original.chaos.anomalies or original._delayed  # chaos is mid-flight at snapshot time
    restored = Engine.restore(original.snapshot())
    for _ in range(60):
        assert dumps(restored.step()) == dumps(original.step())
    assert restored.state.entities == original.state.entities


def test_periodic_snapshots_are_written(tmp_path):
    engine = Engine(chaotic(persistence=Persistence(snapshot_every_ticks=10)))
    for _ in range(25):
        engine.step()
    (snapshot,) = storage.load_snapshots()
    assert snapshot["tick"] == 20


def test_recording_replays_event_for_event():
    original = Engine(chaotic(simulation_id="rec-1", persistence=Persistence(record=True)))
    emitted = [dumps(original.step()) for _ in range(80)]
    original.stop()
    replay = ReplayEngine("rec-1", speed=10)
    replayed = [dumps(replay.step()) for _ in range(80)]
    assert replayed == emitted
    assert any(len(set(e.split('"tick":')[1].split(",")[0] for e in tick)) > 1 for tick in emitted if tick)
    replay.step()
    assert replay.status == "stopped"  # end of recording closes the stream
    with pytest.raises(ValueError, match="read-only"):
        replay.inject(Anomaly(name="x"))


def test_unknown_recording_fails_fast():
    with pytest.raises(ValueError, match="no recording"):
        ReplayEngine("nope")


def test_advance_publishes_only_the_final_tick_but_records_all():
    engine = Engine(chaotic(simulation_id="ff", persistence=Persistence(record=True)))
    queue = engine.subscribe()
    engine.advance(50)
    published = {queue.get_nowait().tick for _ in range(queue.qsize())}
    assert engine.state.tick == 50 and max(published) == 50 and min(published) >= 47  # jitter can release late
    engine.stop()
    lines = storage.recording_path("ff").read_text().splitlines()
    assert len(lines) > 50 * 3


def test_scenario_round_trip(tmp_path):
    config = chaotic()
    for fmt, suffix in (("yaml", ".yaml"), ("json", ".json")):
        path = tmp_path / f"s{suffix}"
        path.write_text(dump_scenario(config, fmt))
        loaded = load_scenario(path)
        assert loaded.model_dump(exclude={"simulation_id"}) == config.model_dump(exclude={"simulation_id"})


def test_simulation_id_cannot_escape_the_data_dir():
    with pytest.raises(ValueError):
        SimulationConfig(simulation_id="../../etc/passwd", domain="x", entities=[microservice("s")])


def test_api_resumes_snapshotted_simulations_after_restart():
    config = chaotic(simulation_id="survivor", persistence=Persistence(snapshot_every_ticks=1))
    with TestClient(app) as http:
        assert http.post("/simulations", json={"config": config.model_dump(mode="json")}).status_code == 201
        http.post("/simulations/survivor/pause")
        tick = http.post("/simulations/survivor/step").json()["tick"]
        yaml_text = http.get("/simulations/survivor/scenario").text
        assert "survivor" not in yaml_text and "random:" in yaml_text
    simulations.clear()  # the process "restarts"
    with TestClient(app) as http:
        state = http.get("/simulations/survivor/state").json()
        assert state["tick"] == tick and state["status"] == "paused"
        assert http.post("/simulations/survivor/advance?ticks=2500").json()["tick"] == tick + 2500
        assert http.post("/simulations/survivor/advance?ticks=0").status_code == 422
        http.delete("/simulations/survivor")
    assert storage.load_snapshots() == []


def test_api_replay():
    config = chaotic(simulation_id="rec-api", persistence=Persistence(record=True))
    engine = Engine(config)
    for _ in range(20):
        engine.step()
    engine.stop()
    with TestClient(app) as http:
        assert "rec-api" in http.get("/recordings").json()
        r = http.post("/replays", json={"recording_id": "rec-api", "speed": 50})
        assert r.status_code == 201
        rid = r.json()["simulation_id"]
        assert rid.startswith("replay-")
        with http.stream("GET", f"/simulations/{rid}/stream") as stream:
            lines = [line for line in stream.iter_lines() if line.startswith("data: ")]
        assert len(lines) >= 20  # the stream ends by itself when the recording does
        assert http.post("/replays", json={"recording_id": "nope"}).status_code == 422
