import pytest
from fastapi.testclient import TestClient

from vibesim.chaos.compiler import compile_chaos
from vibesim.core.engine import Engine
from vibesim.core.state import Anomaly, ChaosRules, EntityConfig, RandomChaos, SimulationConfig, TimelineStep
from vibesim.transport.rest import app


def counters(n: int = 4, **chaos) -> Engine:
    entity = EntityConfig.model_validate(
        {
            "id": "c",
            "type": "counter",
            "count": n,
            "initial_state": {"x": 0.0, "status": "ok"},
            "fields": {"x": {"behavior": "drift", "rate": 1}},
        }
    )
    return Engine(SimulationConfig(domain="test", entities=[entity], chaos_rules=ChaosRules(**chaos)))


def telemetry(events):
    return [e for e in events if e.event_type == "telemetry_update"]


def test_targets_hit_only_listed_entities_and_unknown_targets_fail():
    engine = counters()
    engine.inject(Anomaly(name="freeze", targets=["c-01", "c-03"], set={"x": -5}))
    xs = {e.entity_id: e.data["x"] for e in engine.step()}
    assert xs == {"c-01": -5, "c-02": 1.0, "c-03": -5, "c-04": 1.0}
    with pytest.raises(ValueError, match="unknown entities"):
        engine.inject(Anomaly(name="ghost", targets=["c-99"]))


def test_ramp_moves_gradually_to_target():
    engine = counters(1)
    engine.inject(Anomaly(name="ramp", set={"x": 100}, ramp_ticks=4))
    xs = [engine.step()[0].data["x"] for _ in range(6)]
    assert xs == [25.0, 50.0, 75.0, 100.0, 100.0, 100.0]


def test_delay_and_jitter_hold_events_back():
    engine = counters(1)
    engine.inject(Anomaly(name="lag", delay_ticks=2))
    assert engine.step() == [] and engine.step() == []
    (late,) = engine.step()
    assert late.tick == 1 and late.anomalies_applied == ["lag"]

    jittery = counters(1)
    jittery.inject(Anomaly(name="jitter", jitter_ticks=3))
    ticks = [e.tick for _ in range(40) for e in jittery.step()]
    assert sorted(ticks) != ticks  # out of order
    assert len(ticks) >= 35  # nothing lost, only late


def test_timeline_injects_and_removes_on_schedule():
    engine = counters(
        1,
        timeline=[
            TimelineStep(at_tick=3, inject=Anomaly(name="spike", set={"x": 50})),
            TimelineStep(at_tick=5, remove="spike"),
        ],
    )
    applied = [engine.step()[0].anomalies_applied for _ in range(6)]
    assert applied == [[], [], ["spike"], ["spike"], [], []]


def test_random_chaos_is_seeded_and_incidents_expire():
    catalogue = [Anomaly(name="blip", set={"status": "broken"}, duration_ticks=2)]

    def run():
        engine = counters(1, random=RandomChaos(per_minute=30, catalogue=catalogue))
        return [tuple(engine.step()[-1].anomalies_applied) for _ in range(120)]

    first = run()
    assert first == run()
    names = {n for applied in first for n in applied}
    assert names and all(n.startswith("blip#") for n in names)
    assert max(len(a) for a in first) <= 2  # each incident ends


def test_random_catalogue_needs_durations():
    with pytest.raises(ValueError, match="duration_ticks"):
        RandomChaos(per_minute=1, catalogue=[Anomaly(name="forever")])


VANS = {f"van-0{i}": {"battery_pct": 80.0, "status": "en_route"} for i in range(1, 5)}
SERVICES = {"svc-01": {"cpu_pct": 30.0, "memory_pct": 40.0, "status": "healthy"}}


@pytest.mark.parametrize(
    ("prompt", "entities", "expected"),
    [
        (
            "sudden network drop on half the vans for 30 seconds",
            VANS,
            {"targets": ["van-01", "van-02"], "drop_rate": 0.5, "duration_ticks": 30},
        ),
        ("total outage", VANS, {"drop_rate": 1.0}),
        ("30% packet loss", VANS, {"drop_rate": 0.3}),
        ("dead battery on van-02", VANS, {"targets": ["van-02"], "set": {"battery_pct": 0}}),
        ("spike cpu to 100 gradually", SERVICES, {"set": {"cpu_pct": 100.0}, "ramp_ticks": 10}),
        ("laggy network with jitter", SERVICES, {"delay_ticks": 3, "jitter_ticks": 3}),
        ("force status to delayed for 10 ticks", VANS, {"set": {"status": "delayed"}, "duration_ticks": 10}),
        ("memory leak over 2 minutes", SERVICES, {"set": {"memory_pct": 99}, "ramp_ticks": 120}),
    ],
)
def test_keyword_chaos_compiler(prompt, entities, expected):
    anomaly = compile_chaos(prompt, entities, 1000)
    assert anomaly.model_dump(exclude_defaults=True, exclude={"name"}) == expected


def test_keyword_chaos_compiler_rejects_vague_prompts():
    with pytest.raises(ValueError, match="couldn't tell"):
        compile_chaos("a slowdown", SERVICES, 1000)


def test_chaos_prompt_endpoint():
    with TestClient(app) as http:
        sid = http.post("/simulations", json={"prompt": "3 services"}).json()["simulation_id"]
        http.post(f"/simulations/{sid}/pause")
        r = http.post(f"/simulations/{sid}/chaos/prompt", json={"prompt": "spike cpu to 100 on svc-02"})
        assert r.status_code == 201
        assert r.json()["injected"]["targets"] == ["svc-02"]
        state = http.post(f"/simulations/{sid}/step").json()
        assert state["entities"]["svc-02"]["cpu_pct"] == 100.0
        assert http.post(f"/simulations/{sid}/chaos/prompt", json={"prompt": "vibes"}).status_code == 422
        http.delete(f"/simulations/{sid}")
