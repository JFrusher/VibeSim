import re
import sys
from pathlib import Path

import pytest
import yaml

from vibesim import Engine, SimulationConfig, load_scenario
from vibesim.domains import PLUGINS

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = sorted((ROOT / "examples" / "scenarios").glob("*.yaml"))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda p: p.stem)
def test_example_scenarios_run_offline(path):
    engine = Engine(load_scenario(path))
    for _ in range(400):  # past every scripted timeline step
        engine.step()
    assert engine.state.tick == 400


def test_every_domain_has_an_example():
    domains = {load_scenario(p).domain for p in SCENARIOS}
    assert {"logistics", "devops", "iot", "ecommerce", "finance"} <= domains


def test_config_reference_is_up_to_date():
    sys.path.insert(0, str(ROOT / "scripts"))
    import gen_reference

    assert (ROOT / "docs" / "reference" / "config.md").read_text() == gen_reference.render(), (
        "run: python scripts/gen_reference.py"
    )


def test_plugin_guide_code_runs():
    page = (ROOT / "docs" / "plugins.md").read_text()
    python = re.findall(r"```python\n(.*?)```", page, re.S)
    scenario = re.findall(r"```yaml\n(.*?)```", page, re.S)[0]
    namespace: dict = {}
    try:
        for block in python:
            exec(block, namespace)
        config = SimulationConfig.model_validate({"domain": "physics", **yaml.safe_load(scenario)})
        engine = Engine(config.model_copy(update={"tick_interval_ms": 100}))
        start = engine.state.entities["bob"]["angle"]
        for _ in range(5):
            engine.step()
        bob = engine.state.entities["bob"]
        assert bob["angle"] != start and bob["kinetic_j"] > 0
    finally:
        PLUGINS.pop("pendulum", None)
