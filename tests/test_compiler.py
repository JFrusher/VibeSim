import pytest

from src.core.compiler import compile_prompt


def test_rainy_delivery_fleet():
    config = compile_prompt("Simulate 5 delivery vans in a rainy city with fluctuating traffic and battery drain")
    assert config.domain == "logistics"
    assert len(config.entities) == 5
    rules = config.entities[0].behavior_rules
    assert rules["traffic_delay_prob"] == 0.25
    assert rules["battery_drain_rate"] == 0.3


def test_drain_alone_is_not_rain():
    config = compile_prompt("two vans with battery drain")
    assert len(config.entities) == 2
    assert config.entities[0].behavior_rules["traffic_delay_prob"] == 0.05


def test_devops_prompt_with_tick_rate():
    config = compile_prompt("Simulate four microservices with a memory leak and CPU spikes at 10hz")
    assert config.domain == "devops"
    assert len(config.entities) == 4
    assert config.tick_interval_ms == 100
    assert config.entities[0].behavior_rules["memory_leak_rate"] > 0


def test_unknown_domain_raises():
    with pytest.raises(ValueError, match="domain"):
        compile_prompt("simulate a bakery")
