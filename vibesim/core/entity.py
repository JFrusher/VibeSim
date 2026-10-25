"""Runs one entity's tick: plugin physics, then declarative fields, then the status machine."""

import math
import random
from typing import Any

from vibesim.core.expr import Expr
from vibesim.core.state import Cycle, Derived, Drift, EntityConfig, FieldSpec, MeanRevert, Transition
from vibesim.domains import PLUGINS
from vibesim.domains.base import Plugin, clamp

RESERVED_NAMES = {"t", "tick", "dt"}


class EntityRuntime:
    def __init__(self, config: EntityConfig):
        self.config = config
        self.plugin: Plugin | None = None
        if config.plugin:
            if config.plugin.name not in PLUGINS:
                raise ValueError(f"entity '{config.id}': unknown plugin '{config.plugin.name}'; known: {list(PLUGINS)}")
            self.plugin = PLUGINS[config.plugin.name](config.plugin.params)
        self.fields: list[tuple[str, FieldSpec, Expr | None, Expr | None]] = [
            (name, spec, _compile(spec.expr) if isinstance(spec, Derived) else None, _compile(spec.when))
            for name, spec in config.fields.items()
        ]
        self.machine: list[tuple[Transition, Expr | None]] = [(t, _compile(t.when)) for t in config.machine]
        self._validate_names()

    def initial_state(self) -> dict[str, Any]:
        state = dict(self.config.initial_state)
        if self.plugin:
            self.plugin.init_state(state)
        for name, spec, _, _ in self.fields:
            if name not in state:
                state[name] = spec.base if isinstance(spec, Cycle) else 0.0
        return state

    def tick(self, state: dict[str, Any], tick: int, dt_s: float, rng: random.Random) -> None:
        if self.plugin:
            self.plugin.tick(state, dt_s, rng)
        t = tick * dt_s
        for name, spec, expr, when in self.fields:
            env = {**state, "t": t, "tick": tick, "dt": dt_s}
            if when and not when(env):
                continue
            # bound each field immediately so later fields read physical values
            state[name] = _bound(spec, _advance(spec, state[name], expr, env, t, dt_s, rng))
        if self.plugin:
            self.plugin.clamp(state)
        env = {**state, "t": t, "tick": tick, "dt": dt_s}
        for transition, when in self.machine:
            if not _matches(transition.source, state["status"]):
                continue
            if when and not when(env):
                continue
            if transition.p is not None and rng.random() >= 1 - (1 - transition.p) ** dt_s:
                continue
            state["status"] = transition.target
            break

    def clamp(self, state: dict[str, Any]) -> None:
        if self.plugin:
            self.plugin.clamp(state)
        for name, spec, _, _ in self.fields:
            state[name] = _bound(spec, state[name])

    def _validate_names(self) -> None:
        known = set(self.initial_state()) | set(self.config.fields) | RESERVED_NAMES
        if clash := RESERVED_NAMES & (set(self.config.initial_state) | set(self.config.fields)):
            raise ValueError(f"entity '{self.config.id}': {sorted(clash)} are reserved names")
        if self.machine and "status" not in known:
            raise ValueError(f"entity '{self.config.id}': a machine needs an initial 'status'")
        exprs = [e for _, _, expr, when in self.fields for e in (expr, when) if e] + [w for _, w in self.machine if w]
        for e in exprs:
            if unknown := e.names - known:
                raise ValueError(f"entity '{self.config.id}': '{e.source}' uses unknown names {sorted(unknown)}")


def _bound(spec: FieldSpec, value: float) -> float:
    lo = spec.min if spec.min is not None else -math.inf
    hi = spec.max if spec.max is not None else math.inf
    return round(clamp(value, lo, hi), spec.round) if spec.round is not None else clamp(value, lo, hi)


def _compile(source: str | None) -> Expr | None:
    return Expr(source) if source is not None else None


def _matches(source: str | list[str], status: str) -> bool:
    return source == "*" or status == source or (isinstance(source, list) and status in source)


def _advance(
    spec: FieldSpec, value: float, expr: Expr | None, env: dict[str, Any], t: float, dt_s: float, rng: random.Random
) -> float:
    noise = rng.gauss(0, spec.noise) * math.sqrt(dt_s) if spec.noise else 0.0
    if isinstance(spec, Drift):
        return value + spec.rate * dt_s + noise
    if isinstance(spec, MeanRevert):
        return value + spec.strength * (spec.target - value) * dt_s + noise
    if isinstance(spec, Cycle):
        return spec.base + spec.amplitude * math.sin(2 * math.pi * (t + spec.phase_s) / spec.period_s) + noise
    assert expr is not None
    return float(expr(env)) + noise
