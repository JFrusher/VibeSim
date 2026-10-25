from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vibesim.core import claude_compiler
from vibesim.core.claude_compiler import _Spec, compile_with_claude
from vibesim.core.engine import Engine
from vibesim.transport.rest import app

GREENHOUSE = {
    "domain": "agriculture",
    "tick_interval_ms": 500,
    "entities": [
        {
            "id": "greenhouse",
            "type": "greenhouse",
            "count": 2,
            "initial_state": [{"name": "soil_moisture", "value": 60}, {"name": "status", "value": "ok"}],
            "fields": [
                {"name": "soil_moisture", "behavior": "drift", "rate": -0.5, "min": 0, "max": 100, "round": 1},
                {"name": "light_lux", "behavior": "cycle", "base": 500, "amplitude": 400, "period_s": 60},
            ],
            "machine": [
                {"source": ["ok"], "target": "dry", "when": "soil_moisture < 30"},
                {"source": ["*"], "target": "ok", "p": 0.01},
            ],
        }
    ],
}


class FakeClient:
    def __init__(self, spec: dict | None, stop_reason: str = "end_turn"):
        self.calls: list[dict] = []
        parsed = _Spec.model_validate(spec) if spec else None
        self.beta = SimpleNamespace(
            messages=SimpleNamespace(parse=self._parse(SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)))
        )

    def _parse(self, response):
        def parse(**kwargs):
            self.calls.append(kwargs)
            return response

        return parse


def test_spec_becomes_a_runnable_config():
    client = FakeClient(GREENHOUSE)
    config = compile_with_claude("a greenhouse that dries out", seed=3, client=client)
    assert config.seed == 3 and config.tick_interval_ms == 500
    entity = config.entities[0]
    assert entity.initial_state == {"soil_moisture": 60, "status": "ok"}
    assert entity.machine[1].source == "*"
    engine = Engine(config)
    for _ in range(80):
        engine.step()
    assert engine.state.entities["greenhouse-01"]["status"] in ("ok", "dry")
    assert engine.state.entities["greenhouse-01"]["soil_moisture"] < 60


def test_request_shape():
    client = FakeClient(GREENHOUSE)
    compile_with_claude("a greenhouse", client=client)
    (call,) = client.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is _Spec
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["messages"] == [{"role": "user", "content": "a greenhouse"}]


def test_invalid_expression_from_claude_fails_fast():
    bad = {
        **GREENHOUSE,
        "entities": [
            {**GREENHOUSE["entities"][0], "machine": [{"source": ["ok"], "target": "x", "when": "humidity > 3"}]}
        ],
    }
    with pytest.raises(ValueError, match="unknown names"):
        compile_with_claude("x", client=FakeClient(bad))


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unusable_responses_raise(stop_reason):
    with pytest.raises(ValueError, match=stop_reason):
        compile_with_claude("x", client=FakeClient(GREENHOUSE, stop_reason=stop_reason))


def test_api_compile_endpoint_selects_compiler(monkeypatch):
    seen = []

    def fake(prompt, seed=0, client=None):
        seen.append(prompt)
        return claude_compiler._to_config(_Spec.model_validate(GREENHOUSE), seed)

    monkeypatch.setattr(claude_compiler, "compile_with_claude", fake)
    with TestClient(app) as http:
        keyword = http.post("/compile", json={"prompt": "3 services"}).json()
        assert keyword["domain"] == "devops"
        claude = http.post("/compile", json={"prompt": "a greenhouse", "compiler": "claude"}).json()
        assert claude["domain"] == "agriculture" and seen == ["a greenhouse"]
        r = http.post("/simulations", json={"prompt": "a greenhouse", "compiler": "claude"})
        assert r.status_code == 201 and len(r.json()["entities"]) == 2
        http.delete(f"/simulations/{r.json()['simulation_id']}")
        assert http.post("/compile", json={"prompt": "x", "compiler": "gpt"}).status_code == 422
