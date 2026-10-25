"""VibeSim: promptable, local-first simulations that stream living telemetry.

Use it as a library, no server needed:

    from vibesim import Engine, compile_prompt
    engine = Engine(compile_prompt("3 services with a memory leak"))
    events = engine.step()
"""

from vibesim.core.compiler import compile_prompt, compile_with
from vibesim.core.engine import Engine
from vibesim.core.state import Anomaly, EntityConfig, SimulationConfig, TelemetryEvent
from vibesim.scenario import dump_scenario, load_scenario

__all__ = [
    "Anomaly",
    "Engine",
    "EntityConfig",
    "SimulationConfig",
    "TelemetryEvent",
    "compile_prompt",
    "compile_with",
    "dump_scenario",
    "load_scenario",
]
