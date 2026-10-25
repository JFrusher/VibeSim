# VibeSim Roadmap to v1.0

**Goal:** an open-source, pip-installable promptable emulator. You describe a world, and VibeSim streams living telemetry to dashboards, MQTT, observability stacks and tests. Once compiled, it runs fully offline.

**Delivery:** one PR per phase. Each phase is merged before the next one starts, and CI must be green on every PR.

**Rule for optional features:** every opt-in feature (the LLM compiler, chaos modes, persistence, transports) is switched on in exactly one place, the scenario config. A CLI flag only writes that same field. This gives users choice while keeping one way to do each thing.

---

## Phase 0: Core engine ✅ (PR #1)
Tick engine, logistics and devops domains, chaos overrides/drops/durations, REST + SSE + WebSocket, keyword compiler, 19 tests.

## Phase 1: Foundations ✅
Done first because the package rename breaks every import, and CI makes every later PR verifiable.
- Rename the `src/` package to `vibesim/`, with `python -m vibesim` as the entry point.
- MIT `LICENSE`, plus `CONTRIBUTING.md` and a short `CHANGELOG.md`.
- GitHub Actions: pytest, ruff (lint + format) and mypy `--strict`, on Python 3.11–3.13.
- Freeze the `SimulationConfig` schema, with a `schema_version` field so later phases can evolve it deliberately.

**Done when:** CI is green, mypy strict passes, and the package imports as `vibesim`.

## Phase 2: Hybrid domain engine ✅
The core of "simulate anything".
- **Declarative fields.** Each entity field has a behaviour: `constant`, `drift` (linear), `random_walk`, `mean_revert`, `cycle` (daily/sine), `derived` (a safe expression over other fields, e.g. latency from cpu), plus `min`/`max` clamps.
- **State machines.** States with per-tick transition probabilities and guard conditions (e.g. `en_route → delayed p=0.05`, `→ out_of_battery when battery_pct == 0`).
- **Python plug-ins** for physics the rules can't express (road following, order books). They register through one registry; declarative and plug-in entities can sit in the same simulation.
- **Events beyond telemetry:** state-change events (`status_changed`) emitted next to `telemetry_update`.
- Port devops to pure declarative config to prove the engine works. Logistics stays a plug-in.

**Done when:** a new domain can be written as YAML only, and devops runs with zero Python.

## Phase 3: Domains v1 ✅
- **Logistics + real roads:** the compiler geocodes the named places and fetches a road polyline from public OSRM, once, at creation, cached on disk. Vans follow the polyline at a speed driven by traffic. The runtime makes no network calls.
- **IoT / smart building:** temperature, humidity, CO₂, occupancy driven by a day cycle, energy draw, HVAC state machine.
- **E-commerce:** signups, carts, orders, payment success/failure, inventory depletion and restock, conversion rates on a time-of-day curve.
- **Finance:** price ticks (geometric Brownian motion), a simple order book plug-in, trades, volume spikes.
- **DevOps:** expanded with request rate, error rate, pod restarts and a dependency fan-out between services. *(Fan-out deferred: entities can't yet read each other's state, so it needs a cross-entity expression design.)*

**Done when:** each domain has a preset scenario and tests, and the logistics demo is realistic on a real map.

## Phase 4: Compiler (keyword + optional Claude) ✅
- The keyword compiler covers all five domains plus common modifiers (counts, weather, load, failure rates, tick rate).
- **Claude compiler:** the Anthropic SDK with structured output targeting the `SimulationConfig` JSON schema. Output is validated by the same Pydantic models and rejected with a clear error if invalid. It is called once per creation and never per tick.
- Selection: `compiler: keyword | claude` in the request or scenario. `claude` requires `ANTHROPIC_API_KEY` and fails fast without it, with no silent fallback.
- `POST /compile` returns the config without running it, so users can inspect and tweak it.

**Done when:** the same prompt works through either compiler and produces a valid, runnable config.

## Phase 5: Chaos v2 ✅
All chaos features are opt-in in the scenario's `chaos` block.
- **Natural-language chaos:** `"sudden network drop on half the vans"` becomes an `Anomaly`, using the same compiler choice as above.
- **Scheduled timelines:** `at: 100 → inject X; at: 200 → remove X`, for story-driven runs.
- **Random chaos mode:** incidents drawn from a configurable catalogue at a set rate, seeded so runs are reproducible.
- **Richer anomaly types:** gradual ramps (degrade over N ticks), not just instant overrides, plus latency/jitter on emission.

**Done when:** a scenario file can script a full incident story that replays identically with the same seed.

## Phase 6: Time and persistence ✅
Each feature is independently opt-in.
- **Scenario files:** save and load a full config, including the chaos timeline, as YAML/JSON. `GET /simulations/{id}/scenario` exports it.
- **Snapshots:** periodic state snapshots to disk; on restart, simulations resume from their last snapshot.
- **Record and replay:** write the event stream to JSONL; replay it at original or scaled speed through the same transports.
- **Fast-forward:** `POST /simulations/{id}/advance?ticks=N` runs ticks instantly, and a `time_scale` speeds up the clock.

**Done when:** you can kill the server, restart it, and the simulations carry on, and a recorded run replays byte-identical.

## Phase 7: Transports and integrations ✅
Each one is opt-in per simulation or server.
- **Browser:** CORS config and a tiny dependency-free JS client (`vibesim.js`) for SSE and WebSocket.
- **MQTT:** publishes to a broker, with topic templates such as `vibesim/{sim}/{entity}`.
- **Prometheus:** a `/metrics` endpoint exposing numeric entity fields as gauges.
- **OpenTelemetry:** OTLP metrics export for Grafana/Tempo-style stacks.
- **Embeddable library:** `Engine` usable directly in Python with no server, plus a pytest fixture for backend tests.

**Done when:** each integration has an end-to-end test against a real client or broker in CI (e.g. a Mosquitto service container).

## Phase 8: CLI and web console
- **CLI:** `vibesim run "5 vans in rainy Southampton"`, `vibesim run scenario.yaml`, `vibesim compile "..."`, `vibesim replay run.jsonl`. It starts the server and prints the stream and console URLs.
- **Console:** one static page served by FastAPI, using Leaflet and a chart library from CDN with no build step. It lets you create a simulation from a prompt or file, see vans on a live map and services on live charts, start, pause, step and fast-forward, inject chaos with buttons or plain English, and export the scenario.

**Done when:** `pip install vibesim && vibesim run "..."` opens a working demo.

## Phase 9: Docs, examples, v1.0 release
- MkDocs site on GitHub Pages: quickstart, a scenario schema reference (generated from the Pydantic models), domain guides, an integration guide per transport, and a page on writing a plug-in.
- Examples gallery: a preset scenario per domain, a sample React dashboard consuming the SSE stream, Node-RED/Grafana MQTT recipes and a pytest example.
- PyPI publishing via GitHub Actions trusted publishing on tag, semantic versioning, `v1.0.0`.

**Done when:** a stranger can go from the README to a live dashboard in under 5 minutes.

---

## Open risks
- **PyPI name:** `vibesim` must be checked as free before Phase 9; this affects the package rename in Phase 1.
- **OSRM public server:** it is fair-use only, so heavy use needs a self-hosted URL. Kept as config, not a second code path.
- **Claude structured output:** large configs (many entities) should be generated as templates plus a count, not entity-by-entity.
- **Scope:** Phases 2, 3 and 7 are the largest; each may split into two PRs if review gets heavy.
