"""Compile a natural-language prompt into a SimulationConfig: the offline keyword parser, or Claude.

Runs once at creation, never per tick. Logistics prompts geocode and route here (network, cached).
"""

import random
import re
from typing import Literal

from vibesim import geo
from vibesim.core.state import EntityConfig, SimulationConfig
from vibesim.domains.devops import microservice
from vibesim.domains.ecommerce import store
from vibesim.domains.finance import instrument
from vibesim.domains.iot import room
from vibesim.domains.logistics import delivery_van

# checked in order; the first domain with a matching word wins
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "logistics": ("van", "truck", "lorry", "vehicle", "fleet", "delivery", "deliveries", "courier"),
    "devops": ("server", "service", "microservice", "cpu", "node", "pod", "api", "cluster"),
    "iot": ("sensor", "building", "room", "thermostat", "hvac", "iot", "office", "floor"),
    "ecommerce": ("shop", "store", "ecommerce", "order", "checkout", "cart", "webshop"),
    "finance": ("stock", "market", "ticker", "trading", "crypto", "equity", "equities", "share", "price"),
}
NUMBER_WORDS = {
    w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())
}
DEFAULT_COUNT = 3
DEFAULT_CITY = "Southampton"

PLACE = r"([A-Z][\w'.-]*(?: [A-Z][\w'.-]*)*)"
FROM_TO = re.compile(rf"\bfrom {PLACE} to {PLACE}")
IN_CITY = re.compile(rf"\b(?:in|around|across) (?:[a-z]+ ){{0,2}}{PLACE}")
TICKER = re.compile(r"\b[A-Z]{2,5}\b")


Compiler = Literal["keyword", "claude"]


def compile_with(compiler: Compiler, prompt: str, seed: int = 0) -> SimulationConfig:
    if compiler == "claude":
        from vibesim.core.claude_compiler import compile_with_claude

        return compile_with_claude(prompt, seed)
    return compile_prompt(prompt, seed)


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
    if domain == "logistics":
        entities = _logistics_entities(prompt, words, count, seed)
    elif domain == "devops":
        entities = _devops_entities(text, count)
    elif domain == "iot":
        entities = _iot_entities(text, count)
    elif domain == "ecommerce":
        entities = _ecommerce_entities(text, count)
    else:
        entities = _finance_entities(prompt, text, count)
    return SimulationConfig(domain=domain, tick_interval_ms=tick_interval_ms, seed=seed, entities=entities)


def _detect_domain(words: list[str]) -> str:
    stems = {w.rstrip("s") for w in words} | set(words)
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if stems & set(keywords):
            return domain
    raise ValueError(f"cannot tell the domain from the prompt; mention one of {DOMAIN_KEYWORDS}")


def _logistics_entities(prompt: str, words: list[str], count: int, seed: int) -> list[EntityConfig]:
    text = prompt.lower()
    delay_p = 0.05
    if {"rain", "rainy", "raining", "snow", "snowy", "storm", "stormy", "fog", "foggy"} & set(words):
        delay_p += 0.1
    if any(w in text for w in ("traffic", "rush hour", "congest")):
        delay_p += 0.1
    drain = 0.3 if "drain" in text else 0.1
    routes = _routes(prompt, count, seed)
    return [
        delivery_van(f"van-{i + 1:02d}", path, speed_kmh=speed, delay_p=round(delay_p, 2), drain_pct_per_s=drain)
        for i, (path, speed) in enumerate(routes)
    ]


def _routes(prompt: str, count: int, seed: int) -> list[tuple[list[geo.LatLon], float]]:
    """'from A to B' puts every van on that road route; otherwise random trips inside the named city."""
    if match := FROM_TO.search(prompt):
        start, _ = geo.geocode(match.group(1))
        end, _ = geo.geocode(match.group(2))
        return [geo.road_route(start, end)] * count
    match = IN_CITY.search(prompt)
    _, (south, north, west, east) = geo.geocode(match.group(1) if match else DEFAULT_CITY)
    rng = random.Random(seed)

    def point() -> geo.LatLon:
        # inner 60% of the bounding box keeps trips on the city's roads, not its edges
        return (
            south + (north - south) * rng.uniform(0.2, 0.8),
            west + (east - west) * rng.uniform(0.2, 0.8),
        )

    return [geo.road_route(point(), point()) for _ in range(count)]


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


def _iot_entities(text: str, count: int) -> list[EntityConfig]:
    outdoor = 12.0
    if any(w in text for w in ("hot", "heatwave", "summer")):
        outdoor = 28.0
    elif any(w in text for w in ("cold", "winter", "freezing")):
        outdoor = 2.0
    return [room("room", count=count, outdoor_base_c=outdoor)]


def _ecommerce_entities(text: str, count: int) -> list[EntityConfig]:
    busy = any(w in text for w in ("black friday", "busy", "sale", "launch", "peak"))
    return [store("store", count=count, visitors_per_min=300.0 if busy else 60.0)]


def _finance_entities(prompt: str, text: str, count: int) -> list[EntityConfig]:
    volatility = 0.8 if "crypto" in text or "volatile" in text else 0.3
    tickers = list(dict.fromkeys(TICKER.findall(prompt)))
    ids = [t.lower() for t in tickers] or [f"asset-{i + 1:02d}" for i in range(count)]
    return [instrument(i, annual_volatility=volatility) for i in ids]
