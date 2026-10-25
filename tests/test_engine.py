import asyncio

import pytest

from src.core.engine import Engine
from src.core.state import Anomaly, EntityConfig, SimulationConfig


def devops_config(**kw) -> SimulationConfig:
    return SimulationConfig(
        domain="devops",
        tick_interval_ms=100,
        entities=[EntityConfig(id="svc-01", type="microservice",
                               initial_state={"cpu_pct": 35.0, "memory_pct": 40.0, "latency_ms": 40.0},
                               behavior_rules={"memory_leak_rate": 1.0, "volatility": 0.0})],
        **kw,
    )


def test_step_increments_tick_and_applies_linear_delta():
    engine = Engine(devops_config())
    for expected_tick in range(1, 6):
        (event,) = engine.step()
        assert event.tick == expected_tick == engine.state.tick
    assert engine.state.entities["svc-01"]["memory_pct"] == pytest.approx(45.0)


def test_same_seed_is_deterministic():
    a, b = Engine(devops_config(seed=7)), Engine(devops_config(seed=7))
    for _ in range(20):
        assert [e.data for e in a.step()] == [e.data for e in b.step()]


async def test_run_loop_ticks_and_pause_stops_it():
    engine = Engine(devops_config())
    engine.start()
    await asyncio.sleep(0.35)
    engine.pause()
    ticks = engine.state.tick
    assert ticks >= 3
    await asyncio.sleep(0.25)
    assert engine.state.tick == ticks


async def test_subscriber_gets_events_and_stop_ends_stream():
    engine = Engine(devops_config())
    queue = engine.subscribe()
    engine.step()
    engine.stop()
    assert (await queue.get()).tick == 1
    assert await queue.get() is None
    with pytest.raises(RuntimeError):
        engine.step()


def test_slow_subscriber_is_bounded():
    engine = Engine(devops_config())
    queue = engine.subscribe()
    for _ in range(queue.maxsize + 50):
        engine.step()
    assert queue.qsize() == queue.maxsize


def test_anomaly_expires_after_duration():
    engine = Engine(devops_config())
    engine.inject(Anomaly(name="cpu-spike", set={"cpu_pct": 150}, duration_ticks=2))
    first, second, third = (engine.step()[0] for _ in range(3))
    assert first.data["cpu_pct"] == second.data["cpu_pct"] == 100.0  # clamped
    assert first.data["status"] == "degraded"
    assert first.anomalies_applied == ["cpu-spike"]
    assert third.anomalies_applied == []


def test_drop_rate_suppresses_events():
    engine = Engine(devops_config())
    engine.inject(Anomaly(name="blackout", drop_rate=1.0))
    assert engine.step() == []
    assert engine.state.tick == 1
