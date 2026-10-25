import urllib.request

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """Tests never touch the network or the user's route cache."""
    monkeypatch.setenv("VIBESIM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("VIBESIM_DATA_DIR", str(tmp_path / "data"))

    def no_network(*args, **kwargs):
        raise AssertionError("tests must not hit the network")

    # localhost stays reachable for end-to-end tests against a real server
    real_urlopen = urllib.request.urlopen

    def guarded(url, *args, **kwargs):
        target = url if isinstance(url, str) else url.full_url
        if target.startswith(("http://127.0.0.1", "http://localhost")):
            return real_urlopen(url, *args, **kwargs)
        return no_network()

    monkeypatch.setattr(urllib.request, "urlopen", guarded)
