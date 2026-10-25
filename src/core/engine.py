"""Simulation clock: advances state each tick and fans events out to subscribers."""

import asyncio
import logging
import random
from typing import Literal

from src.chaos.injector import ChaosInjector
from src.core.state import Anomaly, SimulationConfig, SimulationState, TelemetryEvent, utcnow
from src.domains.base import DomainModel
from src.domains.devops import DevOpsDomain
from src.domains.logistics import LogisticsDomain

log = logging.getLogger(__name__)

DOMAINS: dict[str, type[DomainModel]] = {"logistics": LogisticsDomain, "devops": DevOpsDomain}
SUBSCRIBER_QUEUE_SIZE = 1000

Status = Literal["paused", "running", "stopped", "failed"]


class Engine:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.domain = DOMAINS[config.domain]()
        for e in config.entities:
            self.domain.validate(e.id, e.initial_state, e.behavior_rules)
        self.state = SimulationState(config)
        self.chaos = ChaosInjector(config.chaos_rules.active_anomalies)
        self.rng = random.Random(config.seed)
        # separate stream so injecting chaos doesn't shift the base trajectory
        self.chaos_rng = random.Random(config.seed + 1)
        self.status: Status = "paused"
        self._rules = {e.id: e.behavior_rules for e in config.entities}
        self._task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Queue] = set()

    def step(self) -> list[TelemetryEvent]:
        if self.status in ("stopped", "failed"):
            raise RuntimeError(f"simulation is {self.status}")
        tick = self.state.tick + 1
        self.chaos.expire(tick)
        dt_s = self.config.tick_interval_ms / 1000
        events = []
        for entity_id, state in self.state.entities.items():
            anomalies = self.chaos.for_entity(entity_id)
            overrides = {k: v for a in anomalies for k, v in a.set.items()}
            self.domain.apply_chaos(state, overrides)  # tick reacts to forced values
            self.domain.tick(state, self._rules[entity_id], dt_s, self.rng)
            self.domain.apply_chaos(state, overrides)  # payload shows forced values
            if ChaosInjector.should_drop(anomalies, self.chaos_rng):
                continue
            events.append(TelemetryEvent(
                timestamp=utcnow(),
                tick=tick,
                entity_id=entity_id,
                data=dict(state),
                anomalies_applied=[a.name for a in anomalies],
            ))
        self.state.tick = tick
        for event in events:
            self._publish(event)
        return events

    def start(self) -> None:
        if self.status in ("stopped", "failed"):
            raise RuntimeError(f"simulation is {self.status}")
        if self.status == "running":
            return
        self.status = "running"
        self._task = asyncio.get_running_loop().create_task(self._run())
        self._task.add_done_callback(self._on_task_done)

    def pause(self) -> None:
        if self.status != "running":
            raise RuntimeError(f"simulation is {self.status}")
        self._cancel()
        self.status = "paused"

    def stop(self) -> None:
        self._cancel()
        self.status = "stopped"
        for queue in self._subscribers:
            self._offer(queue, None)  # end-of-stream

    def inject(self, anomaly: Anomaly) -> None:
        self.chaos.inject(anomaly, self.state.tick)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def _run(self) -> None:
        interval = self.config.tick_interval_ms / 1000
        while True:
            self.step()
            await asyncio.sleep(interval)

    def _cancel(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _on_task_done(self, task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception():
            log.error("simulation %s crashed", self.config.simulation_id, exc_info=task.exception())
            self.status = "failed"
            for queue in self._subscribers:
                self._offer(queue, None)

    def _publish(self, event: TelemetryEvent) -> None:
        for queue in self._subscribers:
            self._offer(queue, event)

    @staticmethod
    def _offer(queue: asyncio.Queue, item: TelemetryEvent | None) -> None:
        # a slow client loses its oldest event rather than growing memory
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(item)


simulations: dict[str, Engine] = {}
