"""Push integrations that run alongside a simulation: MQTT and OpenTelemetry (OTLP).

Each runs as an asyncio task owned by the Engine; a crash marks the simulation failed.
"""

import asyncio
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from vibesim.core.state import MqttOutput, OtlpOutput

if TYPE_CHECKING:
    from vibesim.core.engine import Engine


async def run_mqtt(engine: "Engine", cfg: MqttOutput) -> None:
    # optional dependency: pip install "vibesim[mqtt]"
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion

    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"vibesim-{engine.config.simulation_id}")
    await asyncio.to_thread(client.connect, cfg.host, cfg.port)
    client.loop_start()
    queue = engine.subscribe()
    try:
        while (event := await queue.get()) is not None:
            topic = cfg.topic.format(
                simulation_id=engine.config.simulation_id, entity_id=event.entity_id, event_type=event.event_type
            )
            client.publish(topic, event.model_dump_json(), qos=cfg.qos)
    finally:
        engine.unsubscribe(queue)
        client.loop_stop()
        client.disconnect()


async def run_otlp(engine: "Engine", cfg: OtlpOutput, reader: Any = None) -> None:
    # optional dependency: pip install "vibesim[otel]"
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.metrics import CallbackOptions, Observation
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    reader = reader or PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=cfg.endpoint), export_interval_millis=cfg.export_interval_ms
    )
    resource = Resource.create({"service.name": "vibesim", "vibesim.simulation_id": engine.config.simulation_id})
    provider = MeterProvider(metric_readers=[reader], resource=resource)

    def observe(options: CallbackOptions) -> Iterable[Observation]:
        for entity_id, state in engine.state.entities.items():
            for field, value in state.items():
                if isinstance(value, int | float) and not isinstance(value, bool):
                    yield Observation(value, {"entity_id": entity_id, "field": field})

    provider.get_meter("vibesim").create_observable_gauge("vibesim.field", callbacks=[observe])
    try:
        await asyncio.Event().wait()  # the reader exports on its own schedule until cancelled
    finally:
        await asyncio.to_thread(provider.shutdown)


def start_outputs(engine: "Engine") -> list[asyncio.Task[None]]:
    loop = asyncio.get_running_loop()
    outputs = engine.config.outputs
    tasks = []
    if outputs.mqtt:
        tasks.append(loop.create_task(run_mqtt(engine, outputs.mqtt)))
    if outputs.otlp:
        tasks.append(loop.create_task(run_otlp(engine, outputs.otlp)))
    return tasks
