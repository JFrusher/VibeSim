"""Microservice domain: CPU, memory and latency random-walk around a baseline."""

import random
from typing import Any

from vibesim.domains.base import DomainModel, clamp


class DevOpsDomain(DomainModel):
    required_state = ("cpu_pct", "memory_pct", "latency_ms")

    def tick(self, state: dict[str, Any], rules: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        volatility = rules.get("volatility", 5.0)
        # mean-revert toward baseline so the walk stays plausible over long runs
        state["cpu_pct"] += rng.gauss(0, volatility) + (rules.get("cpu_baseline", 35.0) - state["cpu_pct"]) * 0.1
        state["memory_pct"] += rng.gauss(0, volatility / 5) + rules.get("memory_leak_rate", 0.0)
        load_factor = (1 + state["cpu_pct"] / 100) ** 3
        state["latency_ms"] = rules.get("latency_baseline_ms", 40.0) * load_factor + rng.uniform(0, 5)
        self.clamp(state)
        state["status"] = "degraded" if state["cpu_pct"] > 90 or state["memory_pct"] > 95 else "healthy"

    def clamp(self, state: dict[str, Any]) -> None:
        state["cpu_pct"] = round(clamp(state["cpu_pct"], 0.0, 100.0), 2)
        state["memory_pct"] = round(clamp(state["memory_pct"], 0.0, 100.0), 2)
        state["latency_ms"] = round(clamp(state["latency_ms"], 0.0, 60_000.0), 2)
