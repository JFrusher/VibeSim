import urllib.request

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """Tests never touch the network or the user's route cache."""
    monkeypatch.setenv("VIBESIM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("VIBESIM_DATA_DIR", str(tmp_path / "data"))

    def no_network(*args, **kwargs):
        raise AssertionError("tests must not hit the network")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
