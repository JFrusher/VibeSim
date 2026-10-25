# Config reference

Generated from the Pydantic models by `scripts/gen_reference.py`. Do not edit by hand.

## SimulationConfig

| Field | Type | Default |
|---|---|---|
| `schema_version` | `Literal[1]` | `1` |
| `simulation_id` | `str` | generated |
| `domain` | `str` | **required** |
| `tick_interval_ms` | `int` | `1000` |
| `time_scale` | `float` | `1.0` |
| `start_time` | `datetime \| None` | `null` |
| `seed` | `int` | `0` |
| `entities` | `list[EntityConfig]` | **required** |
| `chaos_rules` | `ChaosRules` | `"active_anomalies=[] timeline=[] random=None"` |
| `persistence` | `Persistence` | `"snapshot_every_ticks=None record=False"` |
| `outputs` | `Outputs` | `"mqtt=None otlp=None"` |

## EntityConfig

One entity, or `count` identical ones with ids `{id}-01`, `{id}-02`, ...

| Field | Type | Default |
|---|---|---|
| `id` | `str` | **required** |
| `type` | `str` | **required** |
| `count` | `int` | `1` |
| `initial_state` | `dict[str, Any]` | `{}` |
| `fields` | `dict[str, FieldSpec]` | `{}` |
| `machine` | `list[Transition]` | `[]` |
| `plugin` | `PluginRef \| None` | `null` |

## Drift

| Field | Type | Default |
|---|---|---|
| `min` | `float \| None` | `null` |
| `max` | `float \| None` | `null` |
| `noise` | `float` | `0.0` |
| `when` | `str \| None` | `null` |
| `round` | `int \| None` | `null` |
| `behavior` | `Literal['drift']` | **required** |
| `rate` | `float` | `0.0` |

## MeanRevert

| Field | Type | Default |
|---|---|---|
| `min` | `float \| None` | `null` |
| `max` | `float \| None` | `null` |
| `noise` | `float` | `0.0` |
| `when` | `str \| None` | `null` |
| `round` | `int \| None` | `null` |
| `behavior` | `Literal['mean_revert']` | **required** |
| `target` | `float` | **required** |
| `strength` | `float` | `0.1` |

## Cycle

| Field | Type | Default |
|---|---|---|
| `min` | `float \| None` | `null` |
| `max` | `float \| None` | `null` |
| `noise` | `float` | `0.0` |
| `when` | `str \| None` | `null` |
| `round` | `int \| None` | `null` |
| `behavior` | `Literal['cycle']` | **required** |
| `base` | `float` | **required** |
| `amplitude` | `float` | **required** |
| `period_s` | `float` | **required** |
| `phase_s` | `float` | `0.0` |

## Derived

| Field | Type | Default |
|---|---|---|
| `min` | `float \| None` | `null` |
| `max` | `float \| None` | `null` |
| `noise` | `float` | `0.0` |
| `when` | `str \| None` | `null` |
| `round` | `int \| None` | `null` |
| `behavior` | `Literal['derived']` | **required** |
| `expr` | `str` | **required** |

## Transition

Moves `status` from `source` to `target` when `when` holds, with probability `p` per second.

| Field | Type | Default |
|---|---|---|
| `source` | `str \| list[str]` | **required** |
| `target` | `str` | **required** |
| `p` | `float \| None` | `null` |
| `when` | `str \| None` | `null` |

## PluginRef

| Field | Type | Default |
|---|---|---|
| `name` | `str` | **required** |
| `params` | `dict[str, Any]` | `{}` |

## ChaosRules

| Field | Type | Default |
|---|---|---|
| `active_anomalies` | `list[Anomaly]` | `[]` |
| `timeline` | `list[TimelineStep]` | `[]` |
| `random` | `RandomChaos \| None` | `null` |

## Anomaly

| Field | Type | Default |
|---|---|---|
| `name` | `str` | **required** |
| `targets` | `list[str] \| None` | `null` |
| `set` | `dict[str, Any]` | `{}` |
| `ramp_ticks` | `int \| None` | `null` |
| `drop_rate` | `float` | `0.0` |
| `delay_ticks` | `int` | `0` |
| `jitter_ticks` | `int` | `0` |
| `duration_ticks` | `int \| None` | `null` |

## TimelineStep

At `at_tick`, inject an anomaly or remove one by name.

| Field | Type | Default |
|---|---|---|
| `at_tick` | `int` | **required** |
| `inject` | `Anomaly \| None` | `null` |
| `remove` | `str \| None` | `null` |

## RandomChaos

Inject a random catalogue entry `per_minute` times per simulated minute on average.

| Field | Type | Default |
|---|---|---|
| `per_minute` | `float` | **required** |
| `catalogue` | `list[Anomaly]` | **required** |

## Persistence

Opt-in: periodic snapshots (resumed after a restart) and a JSONL recording of every event.

| Field | Type | Default |
|---|---|---|
| `snapshot_every_ticks` | `int \| None` | `null` |
| `record` | `bool` | `false` |

## Outputs

| Field | Type | Default |
|---|---|---|
| `mqtt` | `MqttOutput \| None` | `null` |
| `otlp` | `OtlpOutput \| None` | `null` |

## MqttOutput

Publish every event as JSON to an MQTT broker (needs `vibesim[mqtt]`).

| Field | Type | Default |
|---|---|---|
| `host` | `str` | `"localhost"` |
| `port` | `int` | `1883` |
| `topic` | `str` | `"vibesim/{simulation_id}/{entity_id}"` |
| `qos` | `Literal[0, 1]` | `0` |

## OtlpOutput

Export numeric fields as OpenTelemetry gauges over OTLP/HTTP (needs `vibesim[otel]`).

| Field | Type | Default |
|---|---|---|
| `endpoint` | `str` | `"http://localhost:4318/v1/metrics"` |
| `export_interval_ms` | `int` | `5000` |

## TelemetryEvent

| Field | Type | Default |
|---|---|---|
| `timestamp` | `datetime` | **required** |
| `tick` | `int` | **required** |
| `entity_id` | `str` | **required** |
| `event_type` | `Literal['telemetry_update', 'state_changed']` | `"telemetry_update"` |
| `data` | `dict[str, Any]` | **required** |
| `anomalies_applied` | `list[str]` | `[]` |

## JSON Schema

```json
{
  "$defs": {
    "Anomaly": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "targets": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Targets"
        },
        "set": {
          "additionalProperties": true,
          "default": {},
          "title": "Set",
          "type": "object"
        },
        "ramp_ticks": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ramp Ticks"
        },
        "drop_rate": {
          "default": 0.0,
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Drop Rate",
          "type": "number"
        },
        "delay_ticks": {
          "default": 0,
          "minimum": 0,
          "title": "Delay Ticks",
          "type": "integer"
        },
        "jitter_ticks": {
          "default": 0,
          "minimum": 0,
          "title": "Jitter Ticks",
          "type": "integer"
        },
        "duration_ticks": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Duration Ticks"
        }
      },
      "required": [
        "name"
      ],
      "title": "Anomaly",
      "type": "object"
    },
    "ChaosRules": {
      "additionalProperties": false,
      "properties": {
        "active_anomalies": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Anomaly"
          },
          "title": "Active Anomalies",
          "type": "array"
        },
        "timeline": {
          "default": [],
          "items": {
            "$ref": "#/$defs/TimelineStep"
          },
          "title": "Timeline",
          "type": "array"
        },
        "random": {
          "anyOf": [
            {
              "$ref": "#/$defs/RandomChaos"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "ChaosRules",
      "type": "object"
    },
    "Cycle": {
      "additionalProperties": false,
      "properties": {
        "min": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Min"
        },
        "max": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max"
        },
        "noise": {
          "default": 0.0,
          "minimum": 0.0,
          "title": "Noise",
          "type": "number"
        },
        "when": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "When"
        },
        "round": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Round"
        },
        "behavior": {
          "const": "cycle",
          "title": "Behavior",
          "type": "string"
        },
        "base": {
          "title": "Base",
          "type": "number"
        },
        "amplitude": {
          "title": "Amplitude",
          "type": "number"
        },
        "period_s": {
          "exclusiveMinimum": 0.0,
          "title": "Period S",
          "type": "number"
        },
        "phase_s": {
          "default": 0.0,
          "title": "Phase S",
          "type": "number"
        }
      },
      "required": [
        "behavior",
        "base",
        "amplitude",
        "period_s"
      ],
      "title": "Cycle",
      "type": "object"
    },
    "Derived": {
      "additionalProperties": false,
      "properties": {
        "min": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Min"
        },
        "max": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max"
        },
        "noise": {
          "default": 0.0,
          "minimum": 0.0,
          "title": "Noise",
          "type": "number"
        },
        "when": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "When"
        },
        "round": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Round"
        },
        "behavior": {
          "const": "derived",
          "title": "Behavior",
          "type": "string"
        },
        "expr": {
          "title": "Expr",
          "type": "string"
        }
      },
      "required": [
        "behavior",
        "expr"
      ],
      "title": "Derived",
      "type": "object"
    },
    "Drift": {
      "additionalProperties": false,
      "properties": {
        "min": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Min"
        },
        "max": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max"
        },
        "noise": {
          "default": 0.0,
          "minimum": 0.0,
          "title": "Noise",
          "type": "number"
        },
        "when": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "When"
        },
        "round": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Round"
        },
        "behavior": {
          "const": "drift",
          "title": "Behavior",
          "type": "string"
        },
        "rate": {
          "default": 0.0,
          "title": "Rate",
          "type": "number"
        }
      },
      "required": [
        "behavior"
      ],
      "title": "Drift",
      "type": "object"
    },
    "EntityConfig": {
      "additionalProperties": false,
      "description": "One entity, or `count` identical ones with ids `{id}-01`, `{id}-02`, ...",
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "type": {
          "title": "Type",
          "type": "string"
        },
        "count": {
          "default": 1,
          "minimum": 1,
          "title": "Count",
          "type": "integer"
        },
        "initial_state": {
          "additionalProperties": true,
          "default": {},
          "title": "Initial State",
          "type": "object"
        },
        "fields": {
          "additionalProperties": {
            "discriminator": {
              "mapping": {
                "cycle": "#/$defs/Cycle",
                "derived": "#/$defs/Derived",
                "drift": "#/$defs/Drift",
                "mean_revert": "#/$defs/MeanRevert"
              },
              "propertyName": "behavior"
            },
            "oneOf": [
              {
                "$ref": "#/$defs/Drift"
              },
              {
                "$ref": "#/$defs/MeanRevert"
              },
              {
                "$ref": "#/$defs/Cycle"
              },
              {
                "$ref": "#/$defs/Derived"
              }
            ]
          },
          "default": {},
          "title": "Fields",
          "type": "object"
        },
        "machine": {
          "default": [],
          "items": {
            "$ref": "#/$defs/Transition"
          },
          "title": "Machine",
          "type": "array"
        },
        "plugin": {
          "anyOf": [
            {
              "$ref": "#/$defs/PluginRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "id",
        "type"
      ],
      "title": "EntityConfig",
      "type": "object"
    },
    "MeanRevert": {
      "additionalProperties": false,
      "properties": {
        "min": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Min"
        },
        "max": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max"
        },
        "noise": {
          "default": 0.0,
          "minimum": 0.0,
          "title": "Noise",
          "type": "number"
        },
        "when": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "When"
        },
        "round": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Round"
        },
        "behavior": {
          "const": "mean_revert",
          "title": "Behavior",
          "type": "string"
        },
        "target": {
          "title": "Target",
          "type": "number"
        },
        "strength": {
          "default": 0.1,
          "minimum": 0.0,
          "title": "Strength",
          "type": "number"
        }
      },
      "required": [
        "behavior",
        "target"
      ],
      "title": "MeanRevert",
      "type": "object"
    },
    "MqttOutput": {
      "additionalProperties": false,
      "description": "Publish every event as JSON to an MQTT broker (needs `vibesim[mqtt]`).",
      "properties": {
        "host": {
          "default": "localhost",
          "title": "Host",
          "type": "string"
        },
        "port": {
          "default": 1883,
          "title": "Port",
          "type": "integer"
        },
        "topic": {
          "default": "vibesim/{simulation_id}/{entity_id}",
          "title": "Topic",
          "type": "string"
        },
        "qos": {
          "default": 0,
          "enum": [
            0,
            1
          ],
          "title": "Qos",
          "type": "integer"
        }
      },
      "title": "MqttOutput",
      "type": "object"
    },
    "OtlpOutput": {
      "additionalProperties": false,
      "description": "Export numeric fields as OpenTelemetry gauges over OTLP/HTTP (needs `vibesim[otel]`).",
      "properties": {
        "endpoint": {
          "default": "http://localhost:4318/v1/metrics",
          "title": "Endpoint",
          "type": "string"
        },
        "export_interval_ms": {
          "default": 5000,
          "minimum": 100,
          "title": "Export Interval Ms",
          "type": "integer"
        }
      },
      "title": "OtlpOutput",
      "type": "object"
    },
    "Outputs": {
      "additionalProperties": false,
      "properties": {
        "mqtt": {
          "anyOf": [
            {
              "$ref": "#/$defs/MqttOutput"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "otlp": {
          "anyOf": [
            {
              "$ref": "#/$defs/OtlpOutput"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "title": "Outputs",
      "type": "object"
    },
    "Persistence": {
      "additionalProperties": false,
      "description": "Opt-in: periodic snapshots (resumed after a restart) and a JSONL recording of every event.",
      "properties": {
        "snapshot_every_ticks": {
          "anyOf": [
            {
              "minimum": 1,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Snapshot Every Ticks"
        },
        "record": {
          "default": false,
          "title": "Record",
          "type": "boolean"
        }
      },
      "title": "Persistence",
      "type": "object"
    },
    "PluginRef": {
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "params": {
          "additionalProperties": true,
          "default": {},
          "title": "Params",
          "type": "object"
        }
      },
      "required": [
        "name"
      ],
      "title": "PluginRef",
      "type": "object"
    },
    "RandomChaos": {
      "additionalProperties": false,
      "description": "Inject a random catalogue entry `per_minute` times per simulated minute on average.",
      "properties": {
        "per_minute": {
          "exclusiveMinimum": 0.0,
          "title": "Per Minute",
          "type": "number"
        },
        "catalogue": {
          "items": {
            "$ref": "#/$defs/Anomaly"
          },
          "minItems": 1,
          "title": "Catalogue",
          "type": "array"
        }
      },
      "required": [
        "per_minute",
        "catalogue"
      ],
      "title": "RandomChaos",
      "type": "object"
    },
    "TimelineStep": {
      "additionalProperties": false,
      "description": "At `at_tick`, inject an anomaly or remove one by name.",
      "properties": {
        "at_tick": {
          "minimum": 1,
          "title": "At Tick",
          "type": "integer"
        },
        "inject": {
          "anyOf": [
            {
              "$ref": "#/$defs/Anomaly"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "remove": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Remove"
        }
      },
      "required": [
        "at_tick"
      ],
      "title": "TimelineStep",
      "type": "object"
    },
    "Transition": {
      "additionalProperties": false,
      "description": "Moves `status` from `source` to `target` when `when` holds, with probability `p` per second.",
      "properties": {
        "source": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "items": {
                "type": "string"
              },
              "type": "array"
            }
          ],
          "title": "Source"
        },
        "target": {
          "title": "Target",
          "type": "string"
        },
        "p": {
          "anyOf": [
            {
              "maximum": 1.0,
              "minimum": 0.0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "P"
        },
        "when": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "When"
        }
      },
      "required": [
        "source",
        "target"
      ],
      "title": "Transition",
      "type": "object"
    }
  },
  "properties": {
    "schema_version": {
      "const": 1,
      "default": 1,
      "title": "Schema Version",
      "type": "integer"
    },
    "simulation_id": {
      "pattern": "^[A-Za-z0-9_-]{1,64}$",
      "title": "Simulation Id",
      "type": "string"
    },
    "domain": {
      "title": "Domain",
      "type": "string"
    },
    "tick_interval_ms": {
      "default": 1000,
      "minimum": 100,
      "title": "Tick Interval Ms",
      "type": "integer"
    },
    "time_scale": {
      "default": 1.0,
      "exclusiveMinimum": 0.0,
      "title": "Time Scale",
      "type": "number"
    },
    "start_time": {
      "anyOf": [
        {
          "format": "date-time",
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Start Time"
    },
    "seed": {
      "default": 0,
      "title": "Seed",
      "type": "integer"
    },
    "entities": {
      "items": {
        "$ref": "#/$defs/EntityConfig"
      },
      "minItems": 1,
      "title": "Entities",
      "type": "array"
    },
    "chaos_rules": {
      "$ref": "#/$defs/ChaosRules",
      "default": {
        "active_anomalies": [],
        "timeline": [],
        "random": null
      }
    },
    "persistence": {
      "$ref": "#/$defs/Persistence",
      "default": {
        "snapshot_every_ticks": null,
        "record": false
      }
    },
    "outputs": {
      "$ref": "#/$defs/Outputs",
      "default": {
        "mqtt": null,
        "otlp": null
      }
    }
  },
  "required": [
    "domain",
    "entities"
  ],
  "title": "SimulationConfig",
  "type": "object"
}
```
