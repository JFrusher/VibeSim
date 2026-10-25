"""Testing your own code against VibeSim with the bundled `vibesim` pytest fixture.

pip install vibesim && pytest examples/pytest
"""

from vibesim import Anomaly


def should_page(state: dict) -> bool:
    """The code under test: a toy alerting rule."""
    return state["status"] != "healthy" or state["error_rate_pct"] > 5


def test_quiet_fleet_does_not_page(vibesim):
    engine = vibesim("3 services", seed=7)
    engine.advance(300)
    assert not any(should_page(s) for s in engine.state.entities.values())


def test_cpu_storm_pages(vibesim):
    engine = vibesim("3 services", seed=7)
    engine.inject(Anomaly(name="storm", set={"cpu_pct": 99}, duration_ticks=30))
    engine.advance(5)
    assert all(should_page(s) for s in engine.state.entities.values())


def test_scenario_files_work_too(vibesim):
    engine = vibesim("examples/scenarios/devops-incident.yaml")
    engine.advance(200)  # past the scripted deploy spike
    assert engine.state.tick == 200
