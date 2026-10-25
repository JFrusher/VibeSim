# VibeSim

Local-first, promptable micro-emulator. Describe a world in one sentence, get a stateful simulation streaming live telemetry over SSE or WebSocket. No LLM or network calls at runtime: the prompt is compiled once by a local keyword parser, then ticks run in-process.

## Quickstart

```bash
pip install vibesim
vibesim run "5 delivery vans in rainy Bristol"
```

```
  simulation  0867f0da-… (logistics, 5 entities)
  console     http://127.0.0.1:8000/?sim=0867f0da-…
  stream      http://127.0.0.1:8000/simulations/0867f0da-…/stream
  websocket   ws://127.0.0.1:8000/simulations/0867f0da-…/ws
```

Open the console to watch the vans move on a live map, inject chaos with buttons or plain English, fast-forward, and export the scenario. Point your app at the stream URL.

| Command | |
|---|---|
| `vibesim run "<prompt>"` / `vibesim run scenario.yaml` | serve with a simulation (`--compiler claude`, `--seed`, `--host`, `--port`) |
| `vibesim compile "<prompt>" > scenario.yaml` | write a scenario to edit and re-run |
| `vibesim replay <recording-id> --speed 10` | replay a recorded run |
| `vibesim serve` (or `python -m vibesim`) | the server and console with no simulation |

The server listens on 127.0.0.1 only. Pass `--host 0.0.0.0` to expose it.

## Run over HTTP

```bash
# create (starts ticking immediately)
curl -s -XPOST localhost:8000/simulations -H 'content-type: application/json' \
  -d '{"prompt": "Simulate 5 delivery vans in a rainy city with fluctuating traffic and battery drain"}'

# stream
curl -N localhost:8000/simulations/<id>/stream

# break something
curl -s -XPOST localhost:8000/simulations/<id>/chaos -H 'content-type: application/json' \
  -d '{"name": "dead-battery", "targets": ["van-01"], "set": {"battery_pct": 0}}'

# ...or in plain English
curl -s -XPOST localhost:8000/simulations/<id>/chaos/prompt -H 'content-type: application/json' \
  -d '{"prompt": "sudden network drop on half the vans for 30 seconds"}'
```

You can also POST a full `SimulationConfig` as `{"config": {...}}` instead of a prompt.

## Compilers

A prompt is compiled once, when the simulation is created. Pick the compiler per request:

- `"compiler": "keyword"` (default): offline keyword parser over the built-in presets, the only one that sets up real-road vans and order books.
- `"compiler": "claude"`: Claude (`claude-opus-5-5`, structured output) designs entities from any description, using declarative fields and machines. Needs `pip install "vibesim[claude]"` and `ANTHROPIC_API_KEY`. It fails with a clear error if either is missing, and never quietly falls back to the keyword parser. Requests opt into the API's server-side refusal fallback.

`POST /compile` returns the config without running it, so you can inspect or edit it and then POST it back as `{"config": ...}`.

## Time, persistence and replay

All of these are off unless the config asks for them:

```json
{
  "time_scale": 1440,
  "start_time": "2026-01-01T00:00:00Z",
  "persistence": {"snapshot_every_ticks": 10, "record": true}
}
```

- `time_scale` sets how many simulated seconds pass per wall-clock second (1440 plays a day in a minute). Event `timestamp`s follow the simulated clock from `start_time`, which defaults to the creation time.
- `snapshot_every_ticks` saves the full engine state, RNGs and chaos included. When the server restarts it resumes those simulations exactly where they left off.
- `record` writes every emitted event to `recordings/<id>.jsonl`. `POST /replays {"recording_id", "speed"}` streams it back through SSE/WebSocket event-for-event, then closes the stream.
- `POST /simulations/{id}/advance?ticks=N` fast-forwards. Subscribers see only the final tick, while recordings get everything.
- `GET /simulations/{id}/scenario?format=yaml|json` exports the config as a reusable scenario file.

Files live in `$VIBESIM_DATA_DIR` (default `~/.local/share/vibesim`).

## Integrations

| Consumer | How |
|---|---|
| Browser dashboards | `<script src="http://127.0.0.1:8000/client/vibesim.js">` for a dependency-free client (`VibeSim.create`, `.stream`, `.socket`, `.chaos`). CORS allows `localhost` origins; add others with `VIBESIM_CORS_ORIGINS=https://a.example,https://b.example`. |
| MQTT (Node-RED, Home Assistant, Grafana) | `"outputs": {"mqtt": {"host": "localhost", "port": 1883, "topic": "vibesim/{simulation_id}/{entity_id}"}}` with `pip install "vibesim[mqtt]"`. |
| Prometheus | Scrape `GET /metrics`: `vibesim_field{simulation,entity,field}`, `vibesim_status`, `vibesim_tick`. |
| OpenTelemetry | `"outputs": {"otlp": {"endpoint": "http://localhost:4318/v1/metrics"}}` with `pip install "vibesim[otel]"`. Exports a `vibesim.field` gauge per numeric field. |
| Python tests | Use the library directly, or the auto-registered pytest fixture: `def test_x(vibesim): engine = vibesim("3 services"); engine.advance(100)`. |

If an output can't connect (broker down, for example), the simulation is marked `failed` rather than carrying on silently.

```python
from vibesim import Engine, compile_prompt, Anomaly

engine = Engine(compile_prompt("3 services with a memory leak", seed=1))
engine.advance(600)  # ten simulated minutes
engine.inject(Anomaly(name="outage", drop_rate=1.0, duration_ticks=30))
events = engine.step()
```

## API

| Method | Path | |
|---|---|---|
| POST | `/compile` | `{"prompt", "compiler"?, "seed"?}` returns the config only |
| POST | `/simulations` | `{"prompt": ...}` or `{"config": ...}`, optional `compiler`, `seed` |
| GET | `/simulations` | list simulations |
| GET | `/simulations/{id}/state` | tick, entity state, active anomalies |
| GET | `/simulations/{id}/scenario` | export config (`?format=yaml\|json`) |
| POST | `/simulations/{id}/advance?ticks=N` | fast-forward |
| GET | `/metrics` | Prometheus exposition |
| GET | `/client/vibesim.js` | browser client |
| GET | `/recordings` | recorded runs |
| POST | `/replays` | replay a recording |
| POST | `/simulations/{id}/start\|pause\|step\|stop` | clock control |
| DELETE | `/simulations/{id}` | stop and forget |
| POST | `/simulations/{id}/chaos` | inject an `Anomaly` |
| POST | `/simulations/{id}/chaos/prompt` | plain-English chaos |
| DELETE | `/simulations/{id}/chaos/{name}` | remove it |
| GET | `/simulations/{id}/stream` | SSE telemetry |
| WS | `/simulations/{id}/ws` | telemetry out, `Anomaly` JSON in |

## Chaos

An `Anomaly` has a `name` plus any of the following:

| Field | Effect |
|---|---|
| `targets` | entity ids to hit (omit for all) |
| `set` | state fields forced every tick while active |
| `ramp_ticks` | numeric `set` values move to their target gradually instead of jumping |
| `drop_rate` | share of events lost, 0–1 |
| `delay_ticks`, `jitter_ticks` | events arrive late, and with jitter out of order |
| `duration_ticks` | ends automatically; omit to last until removed |

Plain-English chaos (`POST /simulations/{id}/chaos/prompt`, `{"prompt", "compiler"?}`) understands outages, packet loss (`30%`), latency and jitter, `cpu to 100`, `status to delayed`, shortcuts like "dead battery", "memory leak", "out of stock", targets like "half the vans" or `van-02`, and "for 30 seconds" / "over 2 minutes". `"compiler": "claude"` handles anything else.

Scenario configs can script incidents in `chaos_rules`:

```json
"chaos_rules": {
  "timeline": [
    {"at_tick": 100, "inject": {"name": "storm", "set": {"status": "delayed"}}},
    {"at_tick": 200, "remove": "storm"}
  ],
  "random": {"per_minute": 2, "catalogue": [{"name": "blip", "drop_rate": 1, "duration_ticks": 5}]}
}
```

Random incidents use their own seeded stream: the same `seed` replays the same incidents, and injecting chaos never changes the underlying trajectory.

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
