# VibeSim

Local-first, promptable micro-emulator. Describe a world in one sentence, get a stateful simulation streaming live telemetry over SSE or WebSocket. No LLM or network calls at runtime: the prompt is compiled once by a local keyword parser, then ticks run in-process.

## Run

```bash
pip install -e ".[dev]"
python -m vibesim            # http://127.0.0.1:8000, add --host 0.0.0.0 to expose
```

```bash
# create (starts ticking immediately)
curl -s -XPOST localhost:8000/simulations -H 'content-type: application/json' \
  -d '{"prompt": "Simulate 5 delivery vans in a rainy city with fluctuating traffic and battery drain"}'

# stream
curl -N localhost:8000/simulations/<id>/stream

# break something
curl -s -XPOST localhost:8000/simulations/<id>/chaos -H 'content-type: application/json' \
  -d '{"name": "dead-battery", "entity_id": "van-01", "set": {"battery_pct": 0}}'
```

You can also POST a full `SimulationConfig` as `{"config": {...}}` instead of a prompt.

## API

| Method | Path | |
|---|---|---|
| POST | `/simulations` | `{"prompt": ...}` or `{"config": ...}`, optional `seed` |
| GET | `/simulations/{id}/state` | tick, entity state, active anomalies |
| POST | `/simulations/{id}/start\|pause\|step\|stop` | clock control |
| DELETE | `/simulations/{id}` | stop and forget |
| POST | `/simulations/{id}/chaos` | inject an `Anomaly` |
| DELETE | `/simulations/{id}/chaos/{name}` | remove it |
| GET | `/simulations/{id}/stream` | SSE telemetry |
| WS | `/simulations/{id}/ws` | telemetry out, `Anomaly` JSON in |

An `Anomaly` is `{"name", "entity_id"?, "set"?: {field: value}, "drop_rate"?: 0..1, "duration_ticks"?}`. `set` forces state fields every tick it is active; `drop_rate` suppresses that fraction of events (packet loss). Omit `entity_id` to hit every entity.

## Describing a world

Any domain can be written as config alone. Each entity has an `initial_state`, declarative `fields`, an optional `machine` that drives `status`, and an optional Python `plugin` for physics the rules can't express.

```json
{
  "domain": "smart_building",
  "entities": [{
    "id": "room", "type": "room", "count": 2,
    "initial_state": {"temp_c": 24.0, "status": "cooling"},
    "fields": {
      "temp_c":   {"behavior": "drift", "rate": -0.5, "when": "status == 'cooling'", "round": 1},
      "power_kw": {"behavior": "derived", "expr": "3.5 if status == 'cooling' else 0.1"}
    },
    "machine": [{"source": "cooling", "target": "idle", "when": "temp_c <= 21"}]
  }]
}
```

| Behaviour | Parameters | Each tick |
|---|---|---|
| `drift` | `rate` (units/s) | `x += rate·dt` (rate 0 + `noise` = random walk) |
| `mean_revert` | `target`, `strength` (per s) | moves toward `target` |
| `cycle` | `base`, `amplitude`, `period_s`, `phase_s` | sine wave over sim time `t` |
| `derived` | `expr` | computed from other fields |

Every field also takes `min`, `max`, `noise` (gaussian sd, scaled by √dt), `round` and `when` (it only updates while the expression is true). Fields update in order, so later ones can read earlier ones. Expressions can use state fields, `t` (sim seconds), `tick`, arithmetic, comparisons, `and`/`or`/`not`, `x if c else y`, `in`, and `min max abs round sqrt exp log sin cos clamp pi`.

`machine` transitions are checked in order and the first match wins: `source` (a status, a list, or `"*"`), `target`, plus `when` and/or `p` (probability per second). A status change emits a `state_changed` event next to the regular `telemetry_update`.

`count: N` creates `id-01` to `id-N`.

### Built-in presets

- **logistics**: a `vehicle` plugin follows a `path` of `[lat, lon]` points at `speed_kmh` (slower while `delayed`, stationary otherwise, `arrived` at the end). The battery is a declarative drift, and traffic and running out of battery are machine transitions.
- **devops**: pure config. CPU mean-reverts, memory drifts (a leak), latency is derived from CPU, and status is `healthy`/`degraded`.

Prompt keywords: a number or number word sets the count. rain/snow/storm/fog and traffic raise the odds of delay. "drain" speeds up battery loss. "leak" and "spike" shape devops. "10hz" sets the tick rate. The same `seed` gives the same trajectory.

## Test

```bash
pytest tests/ -v
```
