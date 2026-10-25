# VibeSim

**Living telemetry for apps under construction.** Describe a world in one sentence, and VibeSim runs it as a stateful simulation that streams realistic, story-driven data over SSE, WebSocket, MQTT, Prometheus or OpenTelemetry. Once compiled, it runs fully offline.

```bash
pip install vibesim
vibesim run "5 delivery vans in rainy Bristol"
```

![The VibeSim console: vans on a live map with chaos controls](img/console.png)

Mock data is usually static JSON or random numbers. VibeSim gives a dashboard something worth showing: vans that follow real roads and run their batteries down, services that leak memory and restart, rooms that heat up at midday, stores that sell out on Black Friday. You can break any of it on demand ("sudden network drop on half the vans") to see how your app copes.

- **[Quickstart](quickstart.md)**: run it, open the console, stream it into your app.
- **[Describing a world](worlds.md)**: declarative fields, state machines, plugins and presets.
- **[Compilers](compilers.md)**: the offline keyword parser, or Claude for anything.
- **[Chaos](chaos.md)**: overrides, ramps, packet loss, latency, timelines and random incidents.
- **[Time, persistence and replay](time.md)**: time scale, snapshots, recordings, fast-forward.
- **[Integrations](integrations.md)**: browser, MQTT, Prometheus, OpenTelemetry, Python tests.
- **[Writing a plugin](plugins.md)**: custom physics in Python.
- **[HTTP API](api.md)** and the **[config reference](reference/config.md)**.
