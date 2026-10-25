import pytest

from vibesim.core.compiler import compile_prompt
from vibesim.core.engine import Engine


def test_rainy_delivery_fleet():
    config = compile_prompt("Simulate 5 delivery vans in a rainy city with fluctuating traffic and battery drain")
    assert config.domain == "logistics"
    assert len(config.entities) == 5
    van = config.entities[0]
    assert next(t.p for t in van.machine if t.target == "delayed") == 0.25
    assert van.fields["battery_pct"].rate == -0.3


def test_drain_alone_is_not_rain():
    config = compile_prompt("two vans with battery drain")
    assert len(config.entities) == 2
    assert next(t.p for t in config.entities[0].machine if t.target == "delayed") == 0.05


def test_devops_prompt_with_tick_rate():
    config = compile_prompt("Simulate four microservices with a memory leak and CPU spikes at 10hz")
    assert config.domain == "devops"
    assert config.tick_interval_ms == 100
    (svc,) = config.entities
    assert svc.count == 4
    assert svc.fields["memory_pct"].rate > 0
    assert len(Engine(config).state.entities) == 4


def test_unknown_domain_raises():
    with pytest.raises(ValueError, match="domain"):
        compile_prompt("simulate a bakery")
