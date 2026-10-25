"""Scenario files: a SimulationConfig as YAML (.yaml/.yml) or JSON (.json)."""

import json
from pathlib import Path

import yaml

from vibesim.core.state import SimulationConfig


def load_scenario(path: str | Path) -> SimulationConfig:
    path = Path(path)
    text = path.read_text()
    data = yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else json.loads(text)
    return SimulationConfig.model_validate(data)


def dump_scenario(config: SimulationConfig, fmt: str = "yaml") -> str:
    # no simulation_id: a scenario is a template, each load is a new simulation
    data = config.model_dump(mode="json", exclude_defaults=True, exclude={"simulation_id"})
    if fmt == "json":
        return json.dumps(data, indent=2)
    return yaml.safe_dump(data, sort_keys=False)
