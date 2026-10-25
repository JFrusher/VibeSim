# HTTP API


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

A running server also serves interactive OpenAPI docs at [`/docs`](http://127.0.0.1:8000/docs).
