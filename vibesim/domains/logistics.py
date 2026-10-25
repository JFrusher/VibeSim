"""Fleet domain: a `vehicle` plugin that follows a lat/lon path, plus the delivery-van preset."""

import bisect
import math
import random
from typing import Any

from vibesim.core.state import Drift, EntityConfig, PluginRef, Transition
from vibesim.domains.base import Plugin, clamp

# (start, destination) as (lat, lon)
ROUTES: dict[str, list[tuple[float, float]]] = {
    "southampton_to_winchester": [(50.9097, -1.4043), (51.0632, -1.3080)],
    "southampton_to_portsmouth": [(50.9097, -1.4043), (50.8198, -1.0880)],
    "winchester_to_basingstoke": [(51.0632, -1.3080), (51.2665, -1.0924)],
}

EARTH_KM_PER_DEG_LAT = 111.32
MOVING = ("en_route", "delayed")


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    km_per_deg_lon = EARTH_KM_PER_DEG_LAT * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((b[0] - a[0]) * EARTH_KM_PER_DEG_LAT, (b[1] - a[1]) * km_per_deg_lon)


class VehiclePlugin(Plugin):
    """Moves along `path` at `speed_kmh` while `en_route`, slower while `delayed`, not at all otherwise.

    Owns `lat`, `lon` and `odometer_km`; sets `status` to `arrived` at the end of the path.
    """

    def __init__(self, params: dict[str, Any]):
        path = params.get("path")
        if not isinstance(path, list) or len(path) < 2:
            raise ValueError("vehicle plugin needs 'path': a list of at least two [lat, lon] points")
        if "speed_kmh" not in params:
            raise ValueError("vehicle plugin needs 'speed_kmh'")
        self.path = [(float(lat), float(lon)) for lat, lon in path]
        self.speed_kmh = float(params["speed_kmh"])
        self.delayed_factor = float(params.get("delayed_speed_factor", 0.2))
        self.cumulative_km = [0.0]
        for a, b in zip(self.path, self.path[1:], strict=False):
            self.cumulative_km.append(self.cumulative_km[-1] + _km(a, b))

    @property
    def length_km(self) -> float:
        return self.cumulative_km[-1]

    def init_state(self, state: dict[str, Any]) -> None:
        state.setdefault("odometer_km", 0.0)
        state.setdefault("status", "en_route")
        state["lat"], state["lon"] = self._position(state["odometer_km"])

    def tick(self, state: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        factor = {"en_route": 1.0, "delayed": self.delayed_factor}.get(state["status"], 0.0)
        state["odometer_km"] = min(self.length_km, state["odometer_km"] + self.speed_kmh * factor * dt_s / 3600)
        state["lat"], state["lon"] = self._position(state["odometer_km"])
        if state["odometer_km"] >= self.length_km:
            state["status"] = "arrived"

    def clamp(self, state: dict[str, Any]) -> None:
        state["odometer_km"] = round(clamp(state["odometer_km"], 0.0, self.length_km), 4)
        state["lat"] = round(clamp(state["lat"], -90.0, 90.0), 6)
        state["lon"] = round(clamp(state["lon"], -180.0, 180.0), 6)

    def _position(self, odometer_km: float) -> tuple[float, float]:
        i = min(bisect.bisect_right(self.cumulative_km, odometer_km), len(self.path) - 1)
        seg_start, seg_len = self.cumulative_km[i - 1], self.cumulative_km[i] - self.cumulative_km[i - 1]
        f = (odometer_km - seg_start) / seg_len if seg_len else 1.0
        (lat0, lon0), (lat1, lon1) = self.path[i - 1], self.path[i]
        return lat0 + (lat1 - lat0) * f, lon0 + (lon1 - lon0) * f


def delivery_van(
    id: str, path: list[tuple[float, float]], *, delay_p: float = 0.05, drain_pct_per_s: float = 0.1
) -> EntityConfig:
    return EntityConfig(
        id=id,
        type="delivery_vehicle",
        initial_state={"battery_pct": 100.0, "status": "en_route"},
        plugin=PluginRef(name="vehicle", params={"path": [list(p) for p in path], "speed_kmh": 45}),
        fields={
            "battery_pct": Drift(
                behavior="drift",
                rate=-drain_pct_per_s,
                min=0,
                max=100,
                round=2,
                when=f"status in {MOVING}",
            ),
        },
        machine=[
            Transition(source=["en_route", "delayed"], target="out_of_battery", when="battery_pct <= 0"),
            Transition(source="en_route", target="delayed", p=delay_p),
            Transition(source="delayed", target="en_route", p=0.2),
        ],
    )
