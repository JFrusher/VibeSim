# Quickstart


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
