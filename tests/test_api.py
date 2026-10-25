import json

from fastapi.testclient import TestClient

from vibesim.transport.rest import app


def test_create_control_chaos_and_websocket():
    with TestClient(app) as client:
        r = client.post("/simulations", json={"prompt": "3 services"})
        assert r.status_code == 201, r.text
        sid = r.json()["simulation_id"]
        assert client.post(f"/simulations/{sid}/pause").json()["status"] == "paused"
        tick = client.post(f"/simulations/{sid}/step").json()["tick"]

        r = client.post(f"/simulations/{sid}/chaos", json={"name": "jam", "set": {"status": "degraded"}})
        assert r.status_code == 201
        state = client.post(f"/simulations/{sid}/step").json()
        assert state["tick"] == tick + 1
        assert {e["status"] for e in state["entities"].values()} == {"degraded"}
        assert client.delete(f"/simulations/{sid}/chaos/jam").json()["active_anomalies"] == []

        client.post(f"/simulations/{sid}/start")
        with client.websocket_connect(f"/simulations/{sid}/ws") as ws:
            event = json.loads(ws.receive_text())
            assert event["event_type"] == "telemetry_update"
            ws.send_text(json.dumps({"name": "flat", "targets": [event["entity_id"]], "set": {"cpu_pct": 0}}))
            for _ in range(10):
                event = json.loads(ws.receive_text())
                if event["event_type"] == "telemetry_update" and event["anomalies_applied"] == ["flat"]:
                    break
            assert event["data"]["cpu_pct"] == 0.0

        assert client.delete(f"/simulations/{sid}").status_code == 204
        assert client.get(f"/simulations/{sid}/state").status_code == 404


def test_create_requires_exactly_one_source():
    with TestClient(app) as client:
        assert client.post("/simulations", json={}).status_code == 422
        assert client.post("/simulations", json={"prompt": "a bakery"}).status_code == 422
