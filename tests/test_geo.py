import io
import json
import urllib.request

import pytest

from vibesim import geo

NOMINATIM = [{"lat": "50.90", "lon": "-1.40", "boundingbox": ["50.87", "50.95", "-1.47", "-1.32"]}]
OSRM = {
    "code": "Ok",
    "routes": [{"distance": 10_000, "duration": 1200, "geometry": {"coordinates": [[-1.40, 50.90], [-1.30, 51.00]]}}],
}


@pytest.fixture
def fake_http(monkeypatch):
    calls = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        assert "vibesim" in request.headers["User-agent"]
        body = NOMINATIM if "nominatim" in request.full_url else OSRM
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls


def test_geocode_parses_centre_and_bbox(fake_http):
    assert geo.geocode("Southampton") == ((50.90, -1.40), (50.87, 50.95, -1.47, -1.32))


def test_road_route_returns_lat_lon_path_and_speed(fake_http):
    path, speed = geo.road_route((50.9, -1.4), (51.0, -1.3))
    assert path == [(50.90, -1.40), (51.00, -1.30)]
    assert speed == 30.0  # 10 km in 20 min


def test_responses_are_cached_on_disk(fake_http):
    geo.geocode("Southampton")
    geo.geocode("Southampton")
    assert len(fake_http) == 1


def test_unknown_place_and_no_route_fail_fast(monkeypatch):
    monkeypatch.setattr(geo, "fetch_json", lambda url: [] if "search" in url else {"code": "NoRoute"})
    with pytest.raises(ValueError, match="could not find"):
        geo.geocode("Atlantis")
    with pytest.raises(ValueError, match="no road route"):
        geo.road_route((0, 0), (1, 1))


def test_network_errors_become_value_errors(monkeypatch):
    def down(request, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    with pytest.raises(ValueError, match="geography lookup failed"):
        geo.geocode("Southampton")
