import pytest

from vibesim import geo
from vibesim.core.compiler import compile_prompt
from vibesim.core.engine import Engine

BBOX = (51.0, 51.1, -2.0, -1.9)


@pytest.fixture
def fake_geo(monkeypatch):
    calls = {"geocode": [], "route": []}

    def geocode(place):
        calls["geocode"].append(place)
        return (51.05, -1.95), BBOX

    def road_route(start, end):
        calls["route"].append((start, end))
        return [start, end], 40.0

    monkeypatch.setattr(geo, "geocode", geocode)
    monkeypatch.setattr(geo, "road_route", road_route)
    return calls


def test_rainy_delivery_fleet(fake_geo):
    config = compile_prompt("Simulate 5 delivery vans in a rainy city with fluctuating traffic and battery drain")
    assert config.domain == "logistics"
    assert len(config.entities) == 5
    van = config.entities[0]
    assert next(t.p for t in van.machine if t.target == "delayed") == 0.25
    assert van.fields["battery_pct"].rate == -0.3
    assert van.plugin.params["speed_kmh"] == 40.0
    assert fake_geo["geocode"] == ["Southampton"]  # no capitalised place named


def test_drain_alone_is_not_rain(fake_geo):
    config = compile_prompt("two vans with battery drain")
    assert len(config.entities) == 2
    assert next(t.p for t in config.entities[0].machine if t.target == "delayed") == 0.05


def test_from_to_puts_every_van_on_one_route(fake_geo):
    config = compile_prompt("3 vans from Southampton to Winchester")
    assert fake_geo["geocode"] == ["Southampton", "Winchester"]
    assert len({str(e.plugin.params["path"]) for e in config.entities}) == 1


def test_city_trips_are_seeded_inside_the_bbox(fake_geo):
    compile_prompt("4 vans in rainy Bristol", seed=1)
    assert fake_geo["geocode"] == ["Bristol"]
    points = [p for start_end in fake_geo["route"] for p in start_end]
    assert all(BBOX[0] < lat < BBOX[1] and BBOX[2] < lon < BBOX[3] for lat, lon in points)
    first = list(fake_geo["route"])
    fake_geo["route"].clear()
    compile_prompt("4 vans in rainy Bristol", seed=1)
    assert fake_geo["route"] == first


def test_devops_prompt_with_tick_rate():
    config = compile_prompt("Simulate four microservices with a memory leak and CPU spikes at 10hz")
    assert config.domain == "devops"
    assert config.tick_interval_ms == 100
    (svc,) = config.entities
    assert svc.count == 4
    assert "0.5 * dt" in svc.fields["memory_pct"].expr
    assert len(Engine(config).state.entities) == 4


@pytest.mark.parametrize(
    ("prompt", "domain", "ids"),
    [
        ("6 rooms in a cold office building", "iot", 6),
        ("2 shops on black friday", "ecommerce", 2),
        ("trading BTC and ETH crypto", "finance", 2),
        ("a stock market with 3 stocks", "finance", 3),
    ],
)
def test_other_domains(prompt, domain, ids):
    config = compile_prompt(prompt)
    assert config.domain == domain
    assert len(Engine(config).state.entities) == ids


def test_tickers_become_ids():
    config = compile_prompt("trading BTC and ETH crypto")
    assert [e.id for e in config.entities] == ["btc", "eth"]


def test_unknown_domain_raises():
    with pytest.raises(ValueError, match="domain"):
        compile_prompt("simulate a bakery")
