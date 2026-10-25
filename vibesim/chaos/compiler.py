"""Turn a plain-English failure ("sudden network drop on half the vans for 30 seconds") into an Anomaly.

Keyword rules over the simulation's entity ids and state fields; the Claude variant lives in
vibesim.core.claude_compiler.
"""

import math
import re
from typing import Any, Literal

from vibesim.core.state import Anomaly

NUMBER_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
OUTAGE = ("outage", "blackout", "offline", "disconnect", "down")
LOSSY = ("drop", "loss", "lossy", "flaky", "packet")
LATENCY = ("lag", "laggy", "latency", "delay")
# phrase -> (field prefix, forced value)
SHORTCUTS: dict[str, tuple[str, Any]] = {
    "dead battery": ("battery", 0),
    "battery dies": ("battery", 0),
    "battery drain": ("battery", 0),
    "cpu spike": ("cpu", 100),
    "overload": ("cpu", 100),
    "memory leak": ("memory", 99),
    "out of stock": ("inventory", 0),
    "heatwave": ("outdoor", 38),
}


def compile_chaos_with(
    compiler: Literal["keyword", "claude"], prompt: str, entities: dict[str, dict[str, Any]], tick_interval_ms: int
) -> Anomaly:
    if compiler == "claude":
        from vibesim.core.claude_compiler import compile_chaos_with_claude

        return compile_chaos_with_claude(prompt, entities, tick_interval_ms)
    return compile_chaos(prompt, entities, tick_interval_ms)


def compile_chaos(prompt: str, entities: dict[str, dict[str, Any]], tick_interval_ms: int) -> Anomaly:
    text = prompt.lower()
    words = set(re.findall(r"[a-z]+", text))
    fields = {k for state in entities.values() for k in state}
    effects: dict[str, Any] = {}

    outage = bool(words & set(OUTAGE))
    if outage or words & set(LOSSY):
        percent = re.search(r"(\d+)\s*%", text)
        effects["drop_rate"] = int(percent.group(1)) / 100 if percent else 1.0 if outage else 0.5
    if words & set(LATENCY) or "slow network" in text:
        effects["delay_ticks"] = 3
        effects["jitter_ticks"] = 3 if "jitter" in text or "out of order" in text else 0

    forced: dict[str, Any] = {}
    for phrase, (prefix, value) in SHORTCUTS.items():
        if phrase in text and (name := _field(prefix, fields)):
            forced[name] = value
    for word, number in re.findall(r"\b([a-z_]+)\s+(?:to|=|at)\s+(-?\d+(?:\.\d+)?)", text):
        if name := _field(word, fields):
            forced[name] = float(number)
    if status := re.search(r"status (?:to |= )?([a-z_]+)", text):
        forced["status"] = status.group(1)
    elif "traffic jam" in text or "stuck" in text:
        forced["status"] = "delayed"
    if forced:
        effects["set"] = forced

    if not effects:
        raise ValueError(
            "couldn't tell what to break; mention an outage, packet loss, latency, a field like 'cpu to 100', "
            "or 'status to <name>'"
        )
    if ramp := re.search(r"over (\d+) (second|tick|minute)s?", text):
        effects["ramp_ticks"] = _ticks(int(ramp.group(1)), ramp.group(2), tick_interval_ms)
    elif any(w in text for w in ("gradual", "slowly", "creeping")):
        effects["ramp_ticks"] = 10
    if duration := re.search(r"for (\d+) (second|tick|minute)s?", text):
        effects["duration_ticks"] = _ticks(int(duration.group(1)), duration.group(2), tick_interval_ms)

    return Anomaly(name=_slug(text), targets=_targets(text, sorted(entities)), **effects)


def _field(word: str, fields: set[str]) -> str | None:
    """'battery' -> 'battery_pct'; exact names win."""
    if word in fields:
        return word
    return next((f for f in sorted(fields) if f.startswith(f"{word}_")), None)


def _targets(text: str, ids: list[str]) -> list[str] | None:
    named = [i for i in ids if i in text]
    if named:
        return named
    if "half" in text:
        return ids[: max(1, len(ids) // 2)]
    if count := re.search(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r") of\b", text):
        n = int(count.group(1)) if count.group(1).isdigit() else NUMBER_WORDS[count.group(1)]
        return ids[: max(1, n)]
    return None


def _ticks(amount: int, unit: str, tick_interval_ms: int) -> int:
    if unit == "tick":
        return max(1, amount)
    seconds = amount * (60 if unit == "minute" else 1)
    return max(1, math.ceil(seconds * 1000 / tick_interval_ms))


def _slug(text: str) -> str:
    words = re.findall(r"[a-z]+", text)[:4]
    return "-".join(words) or "anomaly"
