"""Fleet domain: vans drive toward a destination, drain battery, hit traffic."""

import math
import random
from typing import Any

from src.domains.base import DomainModel, clamp

# (start, destination) as (lat, lon)
ROUTES: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "southampton_to_winchester": ((50.9097, -1.4043), (51.0632, -1.3080)),
    "southampton_to_portsmouth": ((50.9097, -1.4043), (50.8198, -1.0880)),
    "winchester_to_basingstoke": ((51.0632, -1.3080), (51.2665, -1.0924)),
}

EARTH_KM_PER_DEG_LAT = 111.32
DELAYED_SPEED_FACTOR = 0.2
DELAY_RECOVERY_PROB = 0.2


class LogisticsDomain(DomainModel):
    required_state = ("lat", "lon", "battery_pct", "status")
    required_rules = ("speed_kmh", "battery_drain_rate", "route")

    def validate(self, entity_id: str, state: dict[str, Any], rules: dict[str, Any]) -> None:
        super().validate(entity_id, state, rules)
        if rules["route"] not in ROUTES:
            raise ValueError(f"entity '{entity_id}' has unknown route '{rules['route']}'; known: {list(ROUTES)}")

    def tick(self, state: dict[str, Any], rules: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        if state["status"] in ("arrived", "out_of_battery"):
            return

        if state["status"] == "delayed":
            if rng.random() < DELAY_RECOVERY_PROB:
                state["status"] = "en_route"
        elif rng.random() < rules.get("traffic_delay_prob", 0.05):
            state["status"] = "delayed"

        speed = rules["speed_kmh"] * (DELAYED_SPEED_FACTOR if state["status"] == "delayed" else 1.0)
        dest_lat, dest_lon = ROUTES[rules["route"]][1]
        km_per_deg_lon = EARTH_KM_PER_DEG_LAT * math.cos(math.radians(state["lat"]))
        d_north_km = (dest_lat - state["lat"]) * EARTH_KM_PER_DEG_LAT
        d_east_km = (dest_lon - state["lon"]) * km_per_deg_lon
        remaining_km = math.hypot(d_north_km, d_east_km)
        step_km = speed * dt_s / 3600

        if step_km >= remaining_km:
            state["lat"], state["lon"], state["status"] = dest_lat, dest_lon, "arrived"
        else:
            f = step_km / remaining_km
            state["lat"] += d_north_km * f / EARTH_KM_PER_DEG_LAT
            state["lon"] += d_east_km * f / km_per_deg_lon

        state["battery_pct"] -= rules["battery_drain_rate"]
        self.clamp(state)

    def clamp(self, state: dict[str, Any]) -> None:
        state["lat"] = clamp(state["lat"], -90.0, 90.0)
        state["lon"] = clamp(state["lon"], -180.0, 180.0)
        state["battery_pct"] = round(clamp(state["battery_pct"], 0.0, 100.0), 3)
        if state["battery_pct"] == 0.0 and state["status"] != "arrived":
            state["status"] = "out_of_battery"
