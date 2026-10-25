# VibeSim over MQTT

Feed Node-RED, Home Assistant or Grafana's MQTT data source.

```bash
pip install "vibesim[mqtt]"
docker run -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf
```

Add an output to any scenario:

```yaml
outputs:
  mqtt:
    host: localhost
    port: 1883
    topic: "plant/{entity_id}/{event_type}"
```

```bash
vibesim run examples/scenarios/iot-office-day.yaml   # with the block above added
mosquitto_sub -t 'plant/#' -v
```

Every event arrives as JSON:
`{"timestamp": "...", "tick": 42, "entity_id": "room-01", "event_type": "telemetry_update", "data": {...}}`.
In Node-RED, use an `mqtt in` node on `plant/+/telemetry_update` followed by a `json` node.
