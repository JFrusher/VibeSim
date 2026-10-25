"""Markets: a `market` plugin (GBM price, order book, trades, volume spikes) and an instrument preset."""

import math
import random
from typing import Any

from vibesim.core.state import EntityConfig, PluginRef
from vibesim.domains.base import Plugin

SECONDS_PER_YEAR = 31_536_000


class MarketPlugin(Plugin):
    """Price follows geometric Brownian motion; a symmetric order book of `depth` levels surrounds it.

    Owns `price`, `bid`, `ask`, `bids`, `asks`, `last_trade_qty`, `volume`.
    """

    def __init__(self, params: dict[str, Any]):
        self.drift = float(params.get("annual_drift", 0.05)) / SECONDS_PER_YEAR
        self.vol = float(params.get("annual_volatility", 0.3)) / math.sqrt(SECONDS_PER_YEAR)
        self.spread_bps = float(params.get("spread_bps", 5))
        self.depth = int(params.get("depth", 5))
        self.tick_size = float(params.get("tick_size", 0.01))
        self.trades_per_s = float(params.get("trades_per_s", 2))
        self.spike_p = float(params.get("spike_p", 0.002))
        if self.vol < 0 or self.depth < 1 or self.tick_size <= 0 or not 0 <= self.spike_p <= 1:
            raise ValueError("market plugin needs annual_volatility >= 0, depth >= 1, tick_size > 0, 0 <= spike_p <= 1")

    def init_state(self, state: dict[str, Any]) -> None:
        if "price" not in state:
            raise ValueError("market plugin needs an initial 'price'")
        state.setdefault("volume", 0)
        state.setdefault("last_trade_qty", 0)
        self._book(state, random.Random(0))

    def tick(self, state: dict[str, Any], dt_s: float, rng: random.Random) -> None:
        spike = rng.random() < 1 - (1 - self.spike_p) ** dt_s
        vol = self.vol * (5 if spike else 1)
        shock = (self.drift - vol**2 / 2) * dt_s + vol * math.sqrt(dt_s) * rng.gauss(0, 1)
        state["price"] = state["price"] * math.exp(shock)
        trades = _poisson(self.trades_per_s * dt_s * (10 if spike else 1), rng)
        qty = _total_qty(trades, rng)
        state["last_trade_qty"] = qty
        state["volume"] += qty
        self._book(state, rng)

    def clamp(self, state: dict[str, Any]) -> None:
        # the true price stays unrounded: per-second moves are often smaller than one tick
        state["price"] = round(max(self.tick_size, state["price"]), 8)

    def _book(self, state: dict[str, Any], rng: random.Random) -> None:
        half = max(self.tick_size, state["price"] * self.spread_bps / 20_000)
        bid = math.floor((state["price"] - half) / self.tick_size) * self.tick_size
        ask = math.ceil((state["price"] + half) / self.tick_size) * self.tick_size
        state["bid"], state["ask"] = round(bid, 8), round(ask, 8)
        step = self.tick_size
        state["bids"] = [[round(bid - i * step, 8), rng.randint(100, 2000)] for i in range(self.depth)]
        state["asks"] = [[round(ask + i * step, 8), rng.randint(100, 2000)] for i in range(self.depth)]


def _total_qty(trades: int, rng: random.Random) -> int:
    """Sum of `trades` uniform 1..100 lot sizes, without looping over thousands of trades on long ticks."""
    if trades > 30:
        return max(0, round(rng.gauss(trades * 50.5, math.sqrt(trades * 833.25))))
    return sum(rng.randint(1, 100) for _ in range(trades))


def _poisson(lam: float, rng: random.Random) -> int:
    if lam > 30:
        # Knuth's threshold exp(-lam) underflows for large lam; the normal approximation is accurate here
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p < threshold:
            return k
        k += 1


def instrument(id: str, *, price: float = 100.0, annual_volatility: float = 0.3) -> EntityConfig:
    return EntityConfig(
        id=id,
        type="instrument",
        initial_state={"symbol": id.upper(), "price": price},
        plugin=PluginRef(name="market", params={"annual_volatility": annual_volatility}),
    )
