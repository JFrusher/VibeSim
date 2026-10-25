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
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, width=120)


class _Dumper(yaml.SafeDumper):
    """Block style, except lists of scalars stay on one line, so [lat, lon] paths stay compact."""


def _represent_list(dumper: yaml.SafeDumper, items: list[object]) -> yaml.Node:
    flat = all(not isinstance(i, dict | list) for i in items)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", items, flow_style=flat)


_Dumper.add_representer(list, _represent_list)
