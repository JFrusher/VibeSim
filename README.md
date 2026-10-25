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

## Compilers

A prompt is compiled once, when the simulation is created. Pick the compiler per request:

- `"compiler": "keyword"` (default): offline keyword parser over the built-in presets, the only one that sets up real-road vans and order books.
- `"compiler": "claude"`: Claude (`claude-opus-5-5`, structured output) designs entities from any description, using declarative fields and machines. Needs `pip install "vibesim[claude]"` and `ANTHROPIC_API_KEY`. It fails with a clear error if either is missing, and never quietly falls back to the keyword parser. Requests opt into the API's server-side refusal fallback.

`POST /compile` returns the config without running it, so you can inspect or edit it and then POST it back as `{"config": ...}`.

## API

| Method | Path | |
|---|---|---|
| POST | `/compile` | `{"prompt", "compiler"?, "seed"?}` returns the config only |
| POST | `/simulations` | `{"prompt": ...}` or `{"config": ...}`, optional `compiler`, `seed` |
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

Every field also takes `min`, `max`, `noise` (gaussian sd, scaled by √dt), `round` and `when` (it only updates while the expression is true). Fields update in order, so later ones can read earlier ones. Expressions can use state fields, `t` (sim seconds), `tick`, `dt` (tick length in seconds, so `x + dt * rate` integrates), arithmetic, comparisons, `and`/`or`/`not`, `x if c else y`, `in`, and `min max abs round sqrt exp log sin cos clamp pi`.

`machine` transitions are checked in order and the first match wins: `source` (a status, a list, or `"*"`), `target`, plus `when` and/or `p` (probability per second). A status change emits a `state_changed` event next to the regular `telemetry_update`.

`count: N` creates `id-01` to `id-N`.

### Built-in presets

| Domain | Prompt words | What runs |
|---|---|---|
| logistics | van, truck, fleet, delivery | `vehicle` plugin on **real road routes** (OSRM), battery drain, traffic delays, `arrived` / `out_of_battery` |
| devops | server, service, api, cluster | requests (daily cycle), CPU, memory leak, latency, error rate, `healthy → degraded → restarting` with restart count |
| iot | room, building, sensor, hvac | occupancy and weather daily cycles, temperature physics, CO₂, humidity, power, thermostat `idle / cooling / heating` |
| ecommerce | shop, store, checkout, cart | visitors, conversion, orders, revenue, payment failures, signups, inventory `in_stock → low_stock → restocking` |
| finance | stock, market, crypto, trading | `market` plugin: GBM price, order book, trades, volume spikes; tickers like `BTC` become entity ids |

Every preset except finance is pure config, and all of them can be overridden by POSTing your own `config`.

Prompt modifiers: a number or number word sets the count, and "10hz" sets the tick rate. Logistics: rain/snow/storm/fog and traffic raise the odds of delay, and "drain" speeds up battery loss. DevOps: "leak" and "spike". IoT: "heatwave", "cold". E-commerce: "black friday", "busy". Finance: "crypto", "volatile". The same `seed` gives the same trajectory.

### Real roads

Logistics prompts name places: `"3 vans from Southampton to Winchester"` puts every van on that road route, `"5 vans in rainy Bristol"` sends each van on a random trip inside the city, and with no place named the city defaults to Southampton. Places are geocoded with OpenStreetMap Nominatim and routed with the public OSRM server **once, when the simulation is created**. Responses are cached in `~/.cache/vibesim` (override with `VIBESIM_CACHE_DIR`), so the same prompt works offline afterwards. For heavy use, point `VIBESIM_OSRM_URL` / `VIBESIM_NOMINATIM_URL` at your own servers.

## Test

```bash
pytest tests/ -v
```
