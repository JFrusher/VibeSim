"""Microservice preset: pure declarative fields, no plugin."""

from vibesim.core.state import Derived, Drift, EntityConfig, MeanRevert, Transition

DEGRADED = "cpu_pct > 90 or memory_pct > 95"


def microservice(
    id: str, *, count: int = 1, cpu_baseline: float = 35.0, volatility: float = 5.0, memory_leak_pct_per_s: float = 0.0
) -> EntityConfig:
    return EntityConfig(
        id=id,
        type="microservice",
        count=count,
        initial_state={"cpu_pct": cpu_baseline, "memory_pct": 40.0, "status": "healthy"},
        fields={
            "cpu_pct": MeanRevert(
                behavior="mean_revert", target=cpu_baseline, strength=0.1, noise=volatility, min=0, max=100, round=2
            ),
            "memory_pct": Drift(
                behavior="drift", rate=memory_leak_pct_per_s, noise=volatility / 5, min=0, max=100, round=2
            ),
            "latency_ms": Derived(behavior="derived", expr="40 * (1 + cpu_pct / 100) ** 3", noise=2, min=0, round=2),
        },
        machine=[
            Transition(source="healthy", target="degraded", when=DEGRADED),
            Transition(source="degraded", target="healthy", when=f"not ({DEGRADED})"),
        ],
    )
