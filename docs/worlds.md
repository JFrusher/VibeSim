# Describing a world


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

## Built-in presets

| Domain | Prompt words | What runs |
|---|---|---|
| logistics | van, truck, fleet, delivery | `vehicle` plugin on **real road routes** (OSRM), battery drain, traffic delays, `arrived` / `out_of_battery` |
| devops | server, service, api, cluster | requests (daily cycle), CPU, memory leak, latency, error rate, `healthy → degraded → restarting` with restart count |
| iot | room, building, sensor, hvac | occupancy and weather daily cycles, temperature physics, CO₂, humidity, power, thermostat `idle / cooling / heating` |
| ecommerce | shop, store, checkout, cart | visitors, conversion, orders, revenue, payment failures, signups, inventory `in_stock → low_stock → restocking` |
| finance | stock, market, crypto, trading | `market` plugin: GBM price, order book, trades, volume spikes; tickers like `BTC` become entity ids |

Every preset except finance is pure config, and all of them can be overridden by POSTing your own `config`.

Prompt modifiers: a number or number word sets the count, and "10hz" sets the tick rate. Logistics: rain/snow/storm/fog and traffic raise the odds of delay, and "drain" speeds up battery loss. DevOps: "leak" and "spike". IoT: "heatwave", "cold". E-commerce: "black friday", "busy". Finance: "crypto", "volatile". The same `seed` gives the same trajectory.

## Real roads

Logistics prompts name places: `"3 vans from Southampton to Winchester"` puts every van on that road route, `"5 vans in rainy Bristol"` sends each van on a random trip inside the city, and with no place named the city defaults to Southampton. Places are geocoded with OpenStreetMap Nominatim and routed with the public OSRM server **once, when the simulation is created**. Responses are cached in `~/.cache/vibesim` (override with `VIBESIM_CACHE_DIR`), so the same prompt works offline afterwards. For heavy use, point `VIBESIM_OSRM_URL` / `VIBESIM_NOMINATIM_URL` at your own servers.
