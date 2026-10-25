# Time, persistence and replay


All of these are off unless the config asks for them:

```json
{
  "time_scale": 1440,
  "start_time": "2026-01-01T00:00:00Z",
  "persistence": {"snapshot_every_ticks": 10, "record": true}
}
```

- `time_scale` sets how many simulated seconds pass per wall-clock second (1440 plays a day in a minute). Event `timestamp`s follow the simulated clock from `start_time`, which defaults to the creation time.
- `snapshot_every_ticks` saves the full engine state, RNGs and chaos included. When the server restarts it resumes those simulations exactly where they left off.
- `record` writes every emitted event to `recordings/<id>.jsonl`. `POST /replays {"recording_id", "speed"}` streams it back through SSE/WebSocket event-for-event, then closes the stream.
- `POST /simulations/{id}/advance?ticks=N` fast-forwards. Subscribers see only the final tick, while recordings get everything.
- `GET /simulations/{id}/scenario?format=yaml|json` exports the config as a reusable scenario file.

Files live in `$VIBESIM_DATA_DIR` (default `~/.local/share/vibesim`).
