"""Regenerate examples/scenarios/*.yaml. Logistics routes come from OSRM (network, cached).

python scripts/gen_examples.py
"""

from datetime import UTC, datetime
from pathlib import Path

from vibesim import Anomaly, SimulationConfig, compile_prompt, dump_scenario
from vibesim.core.state import ChaosRules, RandomChaos, TimelineStep

OUT = Path(__file__).resolve().parent.parent / "examples" / "scenarios"
START = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)


def save(name: str, config: SimulationConfig, header: str) -> None:
    text = dump_scenario(config.model_copy(update={"start_time": START}))
    (OUT / f"{name}.yaml").write_text(f"# {header}\n# Run it: vibesim run examples/scenarios/{name}.yaml\n{text}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    timeline = [
        TimelineStep(
            at_tick=120,
            inject=Anomaly(name="m3-closure", targets=["van-02"], set={"status": "delayed"}, duration_ticks=90),
        ),
        TimelineStep(at_tick=300, inject=Anomaly(name="tunnel", drop_rate=1.0, duration_ticks=20)),
    ]
    save(
        "logistics-southampton",
        compile_prompt("3 delivery vans from Southampton to Winchester in the rain").model_copy(
            update={"chaos_rules": ChaosRules(timeline=timeline)}
        ),
        "Three vans on the real road from Southampton to Winchester: a closure, then a signal-dropping tunnel.",
    )

    timeline = [
        TimelineStep(
            at_tick=60,
            inject=Anomaly(
                name="deploy-spike", targets=["svc-01"], set={"cpu_pct": 97}, ramp_ticks=20, duration_ticks=60
            ),
        ),
        TimelineStep(
            at_tick=150,
            inject=Anomaly(
                name="network-partition",
                targets=["svc-03", "svc-04"],
                drop_rate=0.6,
                delay_ticks=2,
                jitter_ticks=3,
                duration_ticks=45,
            ),
        ),
    ]
    save(
        "devops-incident",
        compile_prompt("4 services with a memory leak").model_copy(
            update={"chaos_rules": ChaosRules(timeline=timeline)}
        ),
        "A bad deploy ramps CPU on svc-01, then a partition drops and delays half the fleet's telemetry.",
    )

    save(
        "iot-office-day",
        compile_prompt("6 rooms in an office in a heatwave").model_copy(update={"time_scale": 1440}),
        "A full office day per minute (time_scale 1440): occupancy, heat and CO2 peak at midday, thermostats respond.",
    )

    incidents = [
        Anomaly(name="payment-outage", set={"payment_failure_pct": 60}, duration_ticks=20),
        Anomaly(name="cdn-hiccup", drop_rate=0.5, duration_ticks=10),
    ]
    save(
        "ecommerce-black-friday",
        compile_prompt("2 shops on black friday").model_copy(
            update={"chaos_rules": ChaosRules(random=RandomChaos(per_minute=3, catalogue=incidents))}
        ),
        "Black Friday traffic with random payment outages and CDN hiccups, seeded so every run tells the same story.",
    )

    save(
        "finance-crypto",
        compile_prompt("trading BTC and ETH crypto"),
        "Two crypto instruments: geometric Brownian motion prices, a live order book and volume spikes.",
    )

    greenhouse = {
        "id": "greenhouse",
        "type": "greenhouse",
        "count": 3,
        "initial_state": {"soil_moisture_pct": 70.0, "status": "ok"},
        "fields": {
            "light_lux": {
                "behavior": "cycle",
                "base": 20000,
                "amplitude": 25000,
                "period_s": 86400,
                "phase_s": -21600,
                "min": 0,
                "round": 0,
            },
            "temp_c": {"behavior": "derived", "expr": "14 + light_lux / 3000", "noise": 0.3, "round": 1},
            "soil_moisture_pct": {
                "behavior": "derived",
                "expr": "soil_moisture_pct + dt * ((0.05 if status == 'watering' else 0) - 0.0004 * temp_c)",
                "min": 0,
                "max": 100,
                "round": 1,
            },
        },
        "machine": [
            {"source": "ok", "target": "dry", "when": "soil_moisture_pct < 35"},
            {"source": "dry", "target": "watering", "p": 0.01},
            {"source": "watering", "target": "ok", "when": "soil_moisture_pct > 75"},
        ],
    }
    save(
        "smart-greenhouse",
        SimulationConfig.model_validate({"domain": "agriculture", "time_scale": 60, "entities": [greenhouse]}),
        "A custom domain in pure YAML, no Python: sunlight drives heat, heat dries the soil, irrigation kicks in.",
    )


if __name__ == "__main__":
    main()
