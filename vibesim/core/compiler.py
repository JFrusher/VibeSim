"""Compile a natural-language prompt into a SimulationConfig.

shortcut: local keyword parser, no LLM; plug an LLM in here if prompts outgrow the keyword tables.
Runs once at creation, never per tick.
"""

import re

from vibesim.core.state import EntityConfig, SimulationConfig
from vibesim.domains.devops import microservice
from vibesim.domains.logistics import ROUTES, delivery_van

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "logistics": ("van", "truck", "lorry", "vehicle", "fleet", "delivery", "deliveries", "courier"),
    "devops": ("server", "service", "microservice", "cpu", "node", "pod", "api", "cluster"),
}
NUMBER_WORDS = {
    w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())
}
DEFAULT_COUNT = 3


def compile_prompt(prompt: str, seed: int = 0) -> SimulationConfig:
    text = prompt.lower()
    words = re.findall(r"[a-z]+|\d+", text)
    domain = _detect_domain(words)
    counts = (int(w) if w.isdigit() else NUMBER_WORDS[w] for w in words if w.isdigit() or w in NUMBER_WORDS)
    count = next(counts, DEFAULT_COUNT)
    if count < 1:
        raise ValueError("prompt must describe at least one entity")
    hz = re.search(r"(\d+)\s*hz", text)
    if hz and int(hz.group(1)) == 0:
        raise ValueError("tick rate must be above 0hz")
    tick_interval_ms = 1000 // int(hz.group(1)) if hz else 1000
    entities = _logistics_entities(text, words, count) if domain == "logistics" else _devops_entities(text, count)
    return SimulationConfig(domain=domain, tick_interval_ms=tick_interval_ms, seed=seed, entities=entities)


def _detect_domain(words: list[str]) -> str:
    stems = {w.rstrip("s") for w in words} | set(words)
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if stems & set(keywords):
            return domain
    raise ValueError(f"cannot tell the domain from the prompt; mention one of {DOMAIN_KEYWORDS}")


def _logistics_entities(text: str, words: list[str], count: int) -> list[EntityConfig]:
    delay_p = 0.05
    if {"rain", "rainy", "raining", "snow", "snowy", "storm", "stormy", "fog", "foggy"} & set(words):
        delay_p += 0.1
    if any(w in text for w in ("traffic", "rush hour", "congest")):
        delay_p += 0.1
    drain = 0.3 if "drain" in text else 0.1
    routes = list(ROUTES.values())
    return [
        delivery_van(f"van-{i + 1:02d}", routes[i % len(routes)], delay_p=round(delay_p, 2), drain_pct_per_s=drain)
        for i in range(count)
    ]


def _devops_entities(text: str, count: int) -> list[EntityConfig]:
    spiky = any(w in text for w in ("spike", "spiky", "high load", "overload"))
    return [
        microservice(
            "svc",
            count=count,
            cpu_baseline=70.0 if spiky else 35.0,
            volatility=12.0 if spiky else 5.0,
            memory_leak_pct_per_s=0.5 if "leak" in text else 0.0,
        )
    ]
