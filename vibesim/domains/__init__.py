from vibesim.domains.base import Plugin
from vibesim.domains.logistics import VehiclePlugin

PLUGINS: dict[str, type[Plugin]] = {"vehicle": VehiclePlugin}
