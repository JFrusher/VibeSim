import json
import os
import socket
import subprocess
import sys
import urllib.request

import pytest
import yaml
from fastapi.testclient import TestClient

from vibesim.cli import config_from, main
from vibesim.scenario import dump_scenario
from vibesim.transport.rest import app


def test_compile_prints_a_scenario(capsys):
    main(["compile", "2 shops on black friday"])
    scenario = yaml.safe_load(capsys.readouterr().out)
    assert scenario["domain"] == "ecommerce" and scenario["entities"][0]["count"] == 2
    main(["compile", "2 services", "--format", "json"])
    assert json.loads(capsys.readouterr().out)["domain"] == "devops"


def test_config_from_scenario_file_or_prompt(tmp_path):
    path = tmp_path / "plant.yaml"
    path.write_text(dump_scenario(config_from("4 rooms", "keyword", 0)))
    assert config_from(str(path), "keyword", 0).domain == "iot"
    assert config_from("2 services", "keyword", 0).domain == "devops"
    with pytest.raises(SystemExit, match="no scenario file"):
        config_from(str(tmp_path / "missing.yaml"), "keyword", 0)


def test_run_starts_a_server_and_prints_urls(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "VIBESIM_DATA_DIR": str(tmp_path)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "vibesim", "run", "2 services", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    try:
        assert proc.stdout is not None
        lines = {}
        for line in proc.stdout:
            if line.strip():
                key, _, value = line.strip().partition(" ")
                lines[key] = value.strip()
            if "websocket" in lines:
                break
        assert lines["console"].startswith(f"http://127.0.0.1:{port}/?sim=")
        with urllib.request.urlopen(lines["stream"], timeout=5) as stream:  # real HTTP, not the blocked mock
            first = stream.readline().decode()
        assert first.startswith("data: ") and '"entity_id":"svc-0' in first
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_console_is_served_with_pinned_cdn_scripts():
    with TestClient(app) as http:
        redirect = http.get("/?sim=abc", follow_redirects=False)
        assert redirect.status_code == 307 and redirect.headers["location"] == "/client/console.html?sim=abc"
        page = http.get("/client/console.html").text
        assert page.count('integrity="sha384-') == 3
