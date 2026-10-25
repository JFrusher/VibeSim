"""Smart-building preset: rooms with a daily occupancy/weather cycle and a thermostat. Pure config."""

from vibesim.core.state import Cycle, Derived, EntityConfig, MeanRevert, Transition

DAY_S = 86_400
HEAT_FLOW = (
    "0.002 * (outdoor_c - temp_c) + 0.0005 * occupancy"
    " - (0.01 if status == 'cooling' else 0) + (0.01 if status == 'heating' else 0)"
)


def room(id: str, *, count: int = 1, setpoint_c: float = 21.0, outdoor_base_c: float = 12.0) -> EntityConfig:
    return EntityConfig(
        id=id,
        type="room",
        count=count,
        initial_state={"setpoint_c": setpoint_c, "temp_c": setpoint_c, "co2_ppm": 420.0, "status": "idle"},
        fields={
            # peaks at midday, empty overnight
            "occupancy": Cycle(
                behavior="cycle", base=8, amplitude=12, period_s=DAY_S, phase_s=-DAY_S / 4, min=0, round=0
            ),
            "outdoor_c": Cycle(
                behavior="cycle", base=outdoor_base_c, amplitude=6, period_s=DAY_S, phase_s=-DAY_S / 3, round=2
            ),
            "temp_c": Derived(behavior="derived", expr=f"temp_c + dt * ({HEAT_FLOW})", noise=0.01, round=2),
            "humidity_pct": MeanRevert(behavior="mean_revert", target=45, noise=0.5, min=0, max=100, round=1),
            "co2_ppm": Derived(
                behavior="derived", expr="co2_ppm + dt * (occupancy * 0.5 - (co2_ppm - 420) * 0.002)", min=400, round=0
            ),
            "power_kw": Derived(
                behavior="derived", expr="0.5 + (3.0 if status != 'idle' else 0) + occupancy * 0.05", round=2
            ),
        },
        machine=[
            Transition(source="idle", target="cooling", when="temp_c > setpoint_c + 1"),
            Transition(source="idle", target="heating", when="temp_c < setpoint_c - 1"),
            Transition(source="cooling", target="idle", when="temp_c <= setpoint_c"),
            Transition(source="heating", target="idle", when="temp_c >= setpoint_c"),
        ],
    )
