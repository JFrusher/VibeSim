"""Compile a prompt into a SimulationConfig with Claude (structured output), once at creation.

Claude fills a list-based schema (structured outputs need closed objects), which is then converted
to a SimulationConfig and checked by building an Engine. Any failure raises ValueError.
"""

from typing import Any, Literal

from pydantic import BaseModel

from vibesim.core.state import EntityConfig, SimulationConfig

MODEL = "claude-opus-5-5"

SYSTEM = """You design simulations for VibeSim, which streams live telemetry to apps under development.
Turn the user's description into entities whose fields evolve every tick. Make it feel alive: noise,
daily cycles, state machines with realistic transitions, and values in physically sensible units and bounds.

Each entity has:
- initial_state: starting values. Include every field a behaviour or expression reads that is not itself
  a behaviour field, and a 'status' if there is a machine.
- fields, updated in order every tick (later fields can read earlier ones):
  - drift: x += rate * dt (units per second); rate 0 with noise is a random walk
  - mean_revert: x moves toward target, closing `strength` of the gap per second
  - cycle: base + amplitude * sin(2*pi*(t + phase_s) / period_s)
  - derived: expr, computed from other fields; `x + dt * (...)` integrates
  Every field may set min, max, noise (gaussian sd scaled by sqrt(dt)), round (decimals) and when
  (an expression; the field only updates while it is true). Leave unused parameters null.
- machine: transitions for 'status', first match wins. source is a list of statuses (["*"] = any),
  target a status, plus when (expression) and/or p (probability per second). At least one of them.

Expressions are Python-like: field names, t (sim seconds), tick, dt (seconds per tick), + - * / ** (literal
exponents up to 10), comparisons, and/or/not, `a if cond else b`, `status in ('a', 'b')`, and the functions
min max abs round sqrt exp log sin cos clamp(x, lo, hi), and pi. No other names. Strings only in comparisons.

Use `count` for identical entities. Keep ids short and lowercase. One tick is tick_interval_ms
(100-60000, default 1000). Cycles with period_s=86400 are a real day, so prefer shorter periods when the
user wants visible change in a demo."""


class _Value(BaseModel):
    name: str
    value: float | str | bool


class _Field(BaseModel):
    name: str
    behavior: Literal["drift", "mean_revert", "cycle", "derived"]
    rate: float | None = None
    target: float | None = None
    strength: float | None = None
    base: float | None = None
    amplitude: float | None = None
    period_s: float | None = None
    phase_s: float | None = None
    expr: str | None = None
    min: float | None = None
    max: float | None = None
    noise: float | None = None
    round: int | None = None
    when: str | None = None


class _Transition(BaseModel):
    source: list[str]
    target: str
    p: float | None = None
    when: str | None = None


class _Entity(BaseModel):
    id: str
    type: str
    count: int
    initial_state: list[_Value]
    fields: list[_Field]
    machine: list[_Transition]


class _Spec(BaseModel):
    domain: str
    tick_interval_ms: int
    entities: list[_Entity]


def compile_with_claude(prompt: str, seed: int = 0, client: Any = None) -> SimulationConfig:
    import anthropic  # optional dependency: pip install "vibesim[claude]"

    client = client or anthropic.Anthropic()
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # on a safety decline, retry on a fallback model chosen by the API
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=_Spec,
        )
    except anthropic.AuthenticationError as e:
        raise ValueError("Claude compiler needs credentials: set ANTHROPIC_API_KEY") from e
    except anthropic.APIError as e:
        raise ValueError(f"Claude compiler request failed: {e}") from e
    if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
        raise ValueError(f"Claude did not produce a simulation (stop_reason={response.stop_reason})")
    return _to_config(response.parsed_output, seed)


def _to_config(spec: _Spec, seed: int) -> SimulationConfig:
    from vibesim.core.engine import Engine

    entities = [
        EntityConfig.model_validate(
            {
                "id": e.id,
                "type": e.type,
                "count": e.count,
                "initial_state": {v.name: v.value for v in e.initial_state},
                "fields": {f.name: f.model_dump(exclude={"name"}, exclude_none=True) for f in e.fields},
                "machine": [
                    {**t.model_dump(exclude_none=True), "source": "*" if t.source == ["*"] else t.source}
                    for t in e.machine
                ],
            }
        )
        for e in spec.entities
    ]
    config = SimulationConfig(domain=spec.domain, tick_interval_ms=spec.tick_interval_ms, seed=seed, entities=entities)
    Engine(config)  # validates expressions, names and plugins; raises ValueError
    return config
