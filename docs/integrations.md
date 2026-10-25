# Integrations


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
