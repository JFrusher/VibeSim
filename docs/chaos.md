# Chaos


An `Anomaly` has a `name` plus any of the following:

| Field | Effect |
|---|---|
| `targets` | entity ids to hit (omit for all) |
| `set` | state fields forced every tick while active |
| `ramp_ticks` | numeric `set` values move to their target gradually instead of jumping |
| `drop_rate` | share of events lost, 0–1 |
| `delay_ticks`, `jitter_ticks` | events arrive late, and with jitter out of order |
| `duration_ticks` | ends automatically; omit to last until removed |

Plain-English chaos (`POST /simulations/{id}/chaos/prompt`, `{"prompt", "compiler"?}`) understands outages, packet loss (`30%`), latency and jitter, `cpu to 100`, `status to delayed`, shortcuts like "dead battery", "memory leak", "out of stock", targets like "half the vans" or `van-02`, and "for 30 seconds" / "over 2 minutes". `"compiler": "claude"` handles anything else.

Scenario configs can script incidents in `chaos_rules`:

```json
"chaos_rules": {
  "timeline": [
    {"at_tick": 100, "inject": {"name": "storm", "set": {"status": "delayed"}}},
    {"at_tick": 200, "remove": "storm"}
  ],
  "random": {"per_minute": 2, "catalogue": [{"name": "blip", "drop_rate": 1, "duration_ticks": 5}]}
}
```

Random incidents use their own seeded stream: the same `seed` replays the same incidents, and injecting chaos never changes the underlying trajectory.
