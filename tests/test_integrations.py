import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import paho.mqtt.client as mqtt
import pytest
from amqtt.broker import Broker
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from paho.mqtt.enums import CallbackAPIVersion

from vibesim import Anomaly, Engine, SimulationConfig
from vibesim.core.state import MqttOutput, OtlpOutput, Outputs
from vibesim.domains.devops import microservice
from vibesim.outputs import run_otlp
from vibesim.transport.rest import app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def services(**outputs) -> SimulationConfig:
    return SimulationConfig(
        domain="devops", tick_interval_ms=100, entities=[microservice("svc", count=2)], outputs=Outputs(**outputs)
    )


async def wait_for(condition, timeout: float = 5.0) -> None:
    for _ in range(int(timeout / 0.05)):
        if condition():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met in time")


async def test_mqtt_output_publishes_events_to_a_real_broker():
    port = free_port()
    broker = Broker(
        {
            "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
            "plugins": {"amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}},
        }
    )
    await broker.start()
    received: list[tuple[str, dict]] = []
    listener = mqtt.Client(CallbackAPIVersion.VERSION2)
    listener.on_message = lambda c, u, m: received.append((m.topic, json.loads(m.payload)))
    listener.connect("127.0.0.1", port)
    listener.subscribe("plant/#")
    listener.loop_start()
    engine = Engine(services(mqtt=MqttOutput(port=port, topic="plant/{entity_id}/{event_type}")))
    try:
        engine.start()
        await wait_for(
            lambda: {t for t, _ in received} >= {"plant/svc-01/telemetry_update", "plant/svc-02/telemetry_update"}
        )
        topic, event = received[0]
        assert event["entity_id"] in topic and "cpu_pct" in event["data"]
    finally:
        engine.stop()
        listener.loop_stop()
        await broker.shutdown()


async def test_unreachable_broker_fails_the_simulation():
    engine = Engine(services(mqtt=MqttOutput(port=free_port())))
    engine.start()
    await wait_for(lambda: engine.status == "failed")


def test_bad_topic_placeholder_rejected():
    with pytest.raises(ValueError, match="placeholders"):
        MqttOutput(topic="x/{tenant}")


async def test_otlp_gauges_cover_every_numeric_field():
    engine = Engine(services())
    engine.step()
    reader = InMemoryMetricReader()
    task = asyncio.create_task(run_otlp(engine, OtlpOutput(), reader=reader))
    await asyncio.sleep(0.1)
    data = reader.get_metrics_data()
    task.cancel()
    (metric,) = [m for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics]
    assert metric.name == "vibesim.field"
    points = {(p.attributes["entity_id"], p.attributes["field"]) for p in metric.data.data_points}
    assert ("svc-01", "cpu_pct") in points and ("svc-02", "latency_ms") in points
    assert not any(field == "status" for _, field in points)


async def test_otlp_exporter_posts_to_a_collector():
    posts: list[bytes] = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):
            posts.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Collector)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/metrics"
    engine = Engine(services(otlp=OtlpOutput(endpoint=endpoint, export_interval_ms=100)))
    try:
        engine.start()
        await wait_for(lambda: posts)
        assert b"vibesim.field" in posts[0] and b"svc-01" in posts[0]
    finally:
        outputs = list(engine._outputs)
        engine.stop()
        await asyncio.gather(*outputs, return_exceptions=True)  # final flush while the collector is still up
        server.shutdown()


def test_prometheus_metrics():
    with TestClient(app) as http:
        sid = http.post("/simulations", json={"prompt": "2 services"}).json()["simulation_id"]
        http.post(f"/simulations/{sid}/pause")
        text = http.get("/metrics").text
        assert f'vibesim_field{{simulation="{sid}",entity="svc-01",field="cpu_pct"}}' in text
        assert f'vibesim_status{{simulation="{sid}",entity="svc-02",status="healthy"}} 1' in text
        assert "# TYPE vibesim_field gauge" in text
        http.delete(f"/simulations/{sid}")


def test_cors_allows_localhost_only():
    with TestClient(app) as http:
        ok = http.options(
            "/simulations", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
        )
        assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
        evil = http.options(
            "/simulations", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
        )
        assert "access-control-allow-origin" not in evil.headers


def test_js_client_is_served():
    with TestClient(app) as http:
        r = http.get("/client/vibesim.js")
        assert r.status_code == 200 and "class Simulation" in r.text


def test_pytest_fixture(vibesim):
    engine = vibesim("3 services", seed=4)
    engine.advance(30)
    engine.inject(Anomaly(name="outage", drop_rate=1.0))
    assert engine.step() == [] and engine.state.tick == 31
