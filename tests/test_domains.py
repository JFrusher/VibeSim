import random

import pytest

from vibesim.core.engine import Engine
from vibesim.core.state import EntityConfig, SimulationConfig
from vibesim.domains.devops import microservice
from vibesim.domains.ecommerce import store
from vibesim.domains.finance import MarketPlugin, instrument
from vibesim.domains.iot import room


def run(entity: EntityConfig, ticks: int, tick_interval_ms: int = 1000) -> dict:
    engine = Engine(SimulationConfig(domain="test", tick_interval_ms=tick_interval_ms, entities=[entity]))
    for _ in range(ticks):
        engine.step()
    return engine.state.entities[entity.instance_ids()[0]]


def test_room_thermostat_cools_back_to_setpoint():
    hot = room("r").model_copy(update={"initial_state": {**room("r").initial_state, "temp_c": 25.0}})
    engine = Engine(SimulationConfig(domain="iot", entities=[hot]))
    statuses = []
    for _ in range(1000):
        engine.step()
        statuses.append(engine.state.entities["r"]["status"])
    assert statuses[0] == "cooling"
    assert engine.state.entities["r"]["temp_c"] <= 21.5
    assert "idle" in statuses


def test_room_fields_stay_physical_and_later_fields_see_bounded_values():
    state = run(room("r"), 60)  # night: the occupancy cycle is below zero before clamping
    assert state["occupancy"] == 0
    assert state["power_kw"] == 0.5 + (3.0 if state["status"] != "idle" else 0)  # occupancy adds nothing
    assert state["co2_ppm"] >= 400


def test_store_sells_runs_out_and_restocks():
    shop = store("s", visitors_per_min=6000, conversion_pct=50)
    engine = Engine(SimulationConfig(domain="ecommerce", entities=[shop]))
    seen = set()
    for _ in range(2000):
        engine.step()
        seen.add(engine.state.entities["s"]["status"])
    state = engine.state.entities["s"]
    assert {"in_stock", "low_stock", "restocking"} <= seen
    assert state["orders_total"] > 0 and state["revenue_total"] > state["orders_total"]
    assert state["inventory"] >= 0


def test_market_book_is_ordered_around_price():
    state = run(instrument("btc", price=100.0, annual_volatility=0.8), 100)
    bids, asks = [p for p, _ in state["bids"]], [p for p, _ in state["asks"]]
    assert bids == sorted(bids, reverse=True) and asks == sorted(asks)
    assert state["bid"] < state["price"] < state["ask"]
    assert state["volume"] > 0


def test_market_price_moves_and_is_seed_deterministic():
    a = run(instrument("x", annual_volatility=0.8), 500)
    b = run(instrument("x", annual_volatility=0.8), 500)
    assert a["price"] != 100.0
    assert a == b


def test_market_requires_a_price():
    with pytest.raises(ValueError, match="price"):
        MarketPlugin({}).init_state({})


def test_market_gbm_volatility_is_tick_rate_independent():
    plugin = MarketPlugin({"annual_volatility": 1.0, "spike_p": 0})
    rng = random.Random(0)
    log_returns = []
    for _ in range(4000):
        state = {"price": 100.0, "volume": 0}
        plugin.tick(state, 3600.0, rng)
        log_returns.append(state["price"] / 100.0 - 1)
    mean = sum(log_returns) / len(log_returns)
    sd = (sum((r - mean) ** 2 for r in log_returns) / len(log_returns)) ** 0.5
    assert sd == pytest.approx(1.0 / (8760**0.5), rel=0.1)  # annual vol scaled to one hour


def test_leaking_service_degrades_restarts_and_recovers():
    svc = microservice("svc", memory_leak_pct_per_s=2.0, volatility=0.0)
    engine = Engine(SimulationConfig(domain="devops", entities=[svc]))
    statuses = []
    for _ in range(300):
        engine.step()
        statuses.append(engine.state.entities["svc"]["status"])
    assert {"degraded", "restarting", "healthy"} <= set(statuses)
    assert engine.state.entities["svc"]["pod_restarts"] >= 1
