"""Compile-time geography: geocode places (Nominatim) and fetch road routes (OSRM).

Only the compiler calls this; results are cached on disk so a prompt hits the network once.
"""

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

NOMINATIM_URL = os.environ.get("VIBESIM_NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OSRM_URL = os.environ.get("VIBESIM_OSRM_URL", "https://router.project-osrm.org")
USER_AGENT = "vibesim/0.1 (+https://github.com/JFrusher/VibeSim)"  # required by Nominatim's usage policy
TIMEOUT_S = 15

LatLon = tuple[float, float]


def cache_dir() -> Path:
    return Path(os.environ.get("VIBESIM_CACHE_DIR", Path.home() / ".cache" / "vibesim"))


def fetch_json(url: str) -> Any:
    """GET `url` as JSON, cached on disk by URL."""
    path = cache_dir() / f"{hashlib.sha256(url.encode()).hexdigest()[:32]}.json"
    if path.exists():
        return json.loads(path.read_text())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            data = json.load(response)
    except OSError as e:
        raise ValueError(f"geography lookup failed ({url}): {e}") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def geocode(place: str) -> tuple[LatLon, tuple[float, float, float, float]]:
    """Return the place's centre and bounding box (south, north, west, east)."""
    query = urllib.parse.urlencode({"q": place, "format": "json", "limit": 1})
    results = fetch_json(f"{NOMINATIM_URL}/search?{query}")
    if not results:
        raise ValueError(f"could not find a place called '{place}'")
    hit = results[0]
    south, north, west, east = (float(v) for v in hit["boundingbox"])
    return (float(hit["lat"]), float(hit["lon"])), (south, north, west, east)


def road_route(start: LatLon, end: LatLon) -> tuple[list[LatLon], float]:
    """Return the driving path as [(lat, lon), ...] and its average speed in km/h."""
    coords = f"{start[1]:.5f},{start[0]:.5f};{end[1]:.5f},{end[0]:.5f}"
    data = fetch_json(f"{OSRM_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson")
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"no road route from {start} to {end}: {data.get('message', data.get('code'))}")
    route = data["routes"][0]
    path = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    speed_kmh = (route["distance"] / 1000) / (route["duration"] / 3600) if route["duration"] else 0.0
    if len(path) < 2 or speed_kmh <= 0:
        raise ValueError(f"route from {start} to {end} is empty")
    return path, round(speed_kmh, 1)
