# Writing a plugin

Most worlds need no Python: declarative [fields and machines](worlds.md) cover drift, cycles, integration and state. Write a plugin when an entity needs physics those rules can't express, such as following a road network or maintaining an order book.

A plugin is one instance per entity, built from its `params`:

```python
import random
from typing import Any

from vibesim.domains.base import Plugin, clamp


class Pendulum(Plugin):
    """Swings with damping. Owns `angle` and `velocity`."""

    def __init__(self, params: dict[str, Any]):
        self.length_m = float(params.get("length_m", 1.0))
        self.damping = float(params.get("damping", 0.05))
        if self.length_m <= 0:
            raise ValueError("pendulum needs length_m > 0")  # rejected when the simulation is created

    def init_state(self, state: dict[str, Any]) -> None:
        state.setdefault("angle", 0.5)
        state.setdefault("velocity", 0.0)

    def tick(self, state: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        accel = -9.81 / self.length_m * state["angle"] - self.damping * state["velocity"]
        state["velocity"] += accel * dt_s
        state["angle"] += state["velocity"] * dt_s

    def clamp(self, state: dict[str, Any]) -> None:
        state["angle"] = clamp(state["angle"], -3.14, 3.14)
```

Register it and reference it by name:

```python
from vibesim.domains import PLUGINS

PLUGINS["pendulum"] = Pendulum
```

```yaml
entities:
  - id: bob
    type: pendulum
    plugin: {name: pendulum, params: {length_m: 2}}
    fields:
      kinetic_j: {behavior: derived, expr: "0.5 * velocity ** 2"}
```

Rules:

- **Validate in `__init__`** and raise `ValueError`, so a bad config fails at creation, not mid-run.
- **Keep per-entity state in `state`**, not on the plugin. Instances of an entity with `count > 1` share one plugin object, and snapshots only save `state`.
- **Use the `rng` you're given** for all randomness, so a seed reproduces the run and snapshots resume exactly.
- **Stay offline.** Fetch anything you need (routes, data) at compile time and pass it in through `params`, as the `vehicle` plugin does with OSRM paths.
- **Scale with `dt_s`.** Ticks can be long (fast-forward, `time_scale`), so make rates per second and keep per-tick work bounded.

The plugin runs first each tick. Declarative fields then read its output, and the status machine runs last.
