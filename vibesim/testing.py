"""pytest plugin (auto-registered on install): a `vibesim` fixture for backend tests.

def test_dashboard_handles_outage(vibesim):
    engine = vibesim("3 services", seed=1)
    engine.advance(100)
    engine.inject(Anomaly(name="outage", drop_rate=1))
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from vibesim.core.compiler import compile_prompt
from vibesim.core.engine import Engine
from vibesim.core.state import SimulationConfig
from vibesim.scenario import load_scenario

Source = str | Path | SimulationConfig


@pytest.fixture
def vibesim() -> Iterator[Callable[..., Engine]]:
    """Factory: a prompt, a scenario file path, or a SimulationConfig in; a ready Engine out."""
    engines: list[Engine] = []

    def make(source: Source, seed: int = 0) -> Engine:
        if isinstance(source, SimulationConfig):
            config = source
        elif isinstance(source, Path) or str(source).endswith((".yaml", ".yml", ".json")):
            config = load_scenario(source)
        else:
            config = compile_prompt(str(source), seed=seed)
        engine = Engine(config)
        engines.append(engine)
        return engine

    yield make
    for engine in engines:
        engine.stop()
