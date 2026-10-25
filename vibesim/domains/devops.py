"""Microservice preset: pure declarative fields, no plugin."""

from vibesim.core.state import Cycle, Derived, EntityConfig, MeanRevert, Transition

DAY_S = 86_400
DEGRADED = "cpu_pct > 90 or memory_pct > 95"


def microservice(
    id: str,
    *,
    count: int = 1,
    cpu_baseline: float = 35.0,
    volatility: float = 5.0,
    memory_leak_pct_per_s: float = 0.0,
    requests_per_s: float = 200.0,
) -> EntityConfig:
    return EntityConfig(
        id=id,
        type="microservice",
        count=count,
        initial_state={"cpu_pct": cpu_baseline, "memory_pct": 40.0, "pod_restarts": 0, "status": "healthy"},
        fields={
            "requests_per_s": Cycle(
                behavior="cycle",
                base=requests_per_s,
                amplitude=requests_per_s / 2,
                period_s=DAY_S,
                noise=requests_per_s / 20,
                min=0,
                round=1,
            ),
            "cpu_pct": MeanRevert(
                behavior="mean_revert", target=cpu_baseline, strength=0.1, noise=volatility, min=0, max=100, round=2
            ),
            # a restart frees leaked memory
            "memory_pct": Derived(
                behavior="derived",
                expr=f"40 if status == 'restarting' else memory_pct + {memory_leak_pct_per_s} * dt",
                noise=volatility / 5,
                min=0,
                max=100,
                round=2,
            ),
            "latency_ms": Derived(behavior="derived", expr="40 * (1 + cpu_pct / 100) ** 3", noise=2, min=0, round=2),
            "error_rate_pct": Derived(
                behavior="derived",
                expr="0.1 + max(0, cpu_pct - 80) * 0.5 + (100 if status == 'restarting' else 0)",
                noise=0.05,
                min=0,
                max=100,
                round=2,
            ),
            "pod_restarts": Derived(behavior="derived", expr="pod_restarts + (1 if status == 'restarting' else 0)"),
        },
        machine=[
            Transition(source="healthy", target="degraded", when=DEGRADED),
            Transition(source="degraded", target="healthy", when=f"not ({DEGRADED})"),
            Transition(source="degraded", target="restarting", p=0.1),
            # one-tick restart: p=1 fires on the next tick at any tick rate
            Transition(source="restarting", target="healthy", p=1.0),
        ],
    )
