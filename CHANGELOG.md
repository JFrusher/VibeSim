# Changelog

## Unreleased

- Core engine: tick loop, logistics and devops domains, chaos overrides, REST/SSE/WebSocket, keyword compiler.
- Package renamed `src` → `vibesim`; `python -m vibesim` serves on 127.0.0.1 by default.
- `SimulationConfig.schema_version` (currently `1`).
- MIT licence, CI (ruff, mypy strict, pytest on 3.11–3.13).
- Hybrid domain engine: declarative fields (`drift`, `mean_revert`, `cycle`, `derived`), a `status` machine, `count` expansion, `vehicle` plugin following a lat/lon path, safe expression language, `state_changed` events. **Breaking:** `behavior_rules` removed; `domain` is now a free-text label.
