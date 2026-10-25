# Changelog

## Unreleased

- Core engine: tick loop, logistics and devops domains, chaos overrides, REST/SSE/WebSocket, keyword compiler.
- Package renamed `src` → `vibesim`; `python -m vibesim` serves on 127.0.0.1 by default.
- `SimulationConfig.schema_version` (currently `1`).
- MIT licence, CI (ruff, mypy strict, pytest on 3.11–3.13).
- Hybrid domain engine: declarative fields (`drift`, `mean_revert`, `cycle`, `derived`), a `status` machine, `count` expansion, `vehicle` plugin following a lat/lon path, safe expression language, `state_changed` events. **Breaking:** `behavior_rules` removed; `domain` is now a free-text label.
- Domains v1: IoT rooms, e-commerce stores, finance `market` plugin (GBM, order book, volume spikes), expanded devops (requests, error rate, restarts). Logistics uses real road routes from OSRM, geocoded with Nominatim, cached on disk. `dt` available in expressions; fields are bounded as soon as they're computed.
- Claude compiler (`"compiler": "claude"`, optional extra `vibesim[claude]`): structured output into a list-based schema, converted and validated into a `SimulationConfig`. `POST /compile`. Compiling runs in a worker thread so other simulations keep ticking.
- Chaos v2: `targets` lists, `ramp_ticks`, `delay_ticks`/`jitter_ticks`, scheduled `timeline`, seeded `random` incidents, plain-English chaos (`POST /simulations/{id}/chaos/prompt`, keyword or Claude). **Breaking:** `Anomaly.entity_id` replaced by `targets`.
- Time and persistence: `time_scale`, simulated-clock timestamps from `start_time`, snapshots with exact resume after restart, JSONL recording and `POST /replays`, fast-forward `advance`, YAML/JSON scenario files and export, `GET /simulations`. `simulation_id` is restricted to `[A-Za-z0-9_-]`.
