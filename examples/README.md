# Examples

| | |
|---|---|
| [`scenarios/`](scenarios) | One ready-to-run scenario per domain, plus a custom pure-YAML domain: `vibesim run examples/scenarios/<name>.yaml` |
| [`react-dashboard/`](react-dashboard) | A no-build React dashboard reading the SSE stream, showing staleness when chaos drops telemetry |
| [`pytest/`](pytest) | Testing your own alerting code with the `vibesim` fixture |
| [`prometheus/`](prometheus) | Scrape config for Prometheus/Grafana |
| [`mqtt/`](mqtt) | Node-RED / Home Assistant / Grafana recipe |

`python scripts/gen_examples.py` regenerates the scenarios.
