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

## Domains

- **logistics**: vans drive a named route (`southampton_to_winchester`, `southampton_to_portsmouth`, `winchester_to_basingstoke`), drain battery per tick, randomly get stuck in traffic (`delayed`), end `arrived` or `out_of_battery`.
- **devops**: services with mean-reverting CPU, optional memory leak, latency that rises with CPU, `healthy`/`degraded`.

Prompt keywords: a number or number word sets the count; rain/snow/storm/fog and traffic raise delay odds; "drain" speeds battery loss; "leak", "spike" shape devops; "10hz" sets the tick rate. Same `seed` gives the same trajectory.

## Test

```bash
pytest tests/ -v
```
