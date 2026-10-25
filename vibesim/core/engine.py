"""Simulation clock: advances state each tick and fans events out to subscribers."""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import IO, Any, Literal

from vibesim import storage
from vibesim.chaos.injector import ChaosInjector
from vibesim.core.entity import EntityRuntime
from vibesim.core.state import Anomaly, SimulationConfig, SimulationState, TelemetryEvent, utcnow

log = logging.getLogger(__name__)

SUBSCRIBER_QUEUE_SIZE = 1000

# None marks end-of-stream
Subscriber = asyncio.Queue[TelemetryEvent | None]
Status = Literal["paused", "running", "stopped", "failed"]


class Engine:
    def __init__(self, config: SimulationConfig):
        # pin the simulated clock so timestamps (and recordings) are reproducible from the config
        self.config = config if config.start_time else config.model_copy(update={"start_time": utcnow()})
        # instances of the same EntityConfig share one runtime; runtimes hold no per-instance state
        self.runtimes: dict[str, EntityRuntime] = {}
        for entity in config.entities:
            runtime = EntityRuntime(entity)
            for entity_id in entity.instance_ids():
                if entity_id in self.runtimes:
                    raise ValueError(f"duplicate entity id '{entity_id}'")
                self.runtimes[entity_id] = runtime
        self.state = SimulationState({eid: rt.initial_state() for eid, rt in self.runtimes.items()})
        self.chaos = ChaosInjector(config.chaos_rules, self.runtimes)
        self.rng = random.Random(config.seed)
        # separate stream so injecting chaos doesn't shift the base trajectory
        self.chaos_rng = random.Random(config.seed + 1)
        self.status: Status = "paused"
        self._task: asyncio.Task[None] | None = None
        self._subscribers: set[Subscriber] = set()
        self._delayed: list[tuple[int, TelemetryEvent]] = []  # (release tick, event) held back by chaos
        self._recording: IO[str] | None = None
        if self.config.persistence.record:
            path = storage.recording_path(self.config.simulation_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._recording = path.open("a")
            if path.stat().st_size == 0:
                self._recording.write(self.config.model_dump_json() + "\n")

    @property
    def dt_s(self) -> float:
        """Simulated seconds per tick."""
        return self.config.tick_interval_ms / 1000 * self.config.time_scale

    def sim_time(self, tick: int) -> datetime:
        assert self.config.start_time is not None
        return self.config.start_time + timedelta(seconds=tick * self.dt_s)

    def step(self, publish: bool = True) -> list[TelemetryEvent]:
        if self.status in ("stopped", "failed"):
            raise RuntimeError(f"simulation is {self.status}")
        tick = self.state.tick + 1
        dt_s = self.dt_s
        now = self.sim_time(tick)
        self.chaos.begin_tick(tick, dt_s, self.chaos_rng)
        events: list[TelemetryEvent] = []
        for entity_id, state in self.state.entities.items():
            runtime = self.runtimes[entity_id]
            anomalies = self.chaos.for_entity(entity_id)
            overrides = self.chaos.overrides(entity_id, state, tick)
            previous_status = state.get("status")
            state.update(overrides)  # tick reacts to forced values
            runtime.clamp(state)
            runtime.tick(state, tick, dt_s, self.rng)
            state.update(overrides)  # payload shows forced values
            runtime.clamp(state)
            if ChaosInjector.should_drop(anomalies, self.chaos_rng):
                continue
            entity_events = []
            if state.get("status") != previous_status:
                entity_events.append(
                    TelemetryEvent(
                        timestamp=now,
                        tick=tick,
                        entity_id=entity_id,
                        event_type="state_changed",
                        data={"field": "status", "from": previous_status, "to": state["status"]},
                        anomalies_applied=[a.name for a in anomalies],
                    )
                )
            entity_events.append(
                TelemetryEvent(
                    timestamp=now,
                    tick=tick,
                    entity_id=entity_id,
                    data=dict(state),
                    anomalies_applied=[a.name for a in anomalies],
                )
            )
            if delay := ChaosInjector.delay(anomalies, self.chaos_rng):
                self._delayed.extend((tick + delay, e) for e in entity_events)
            else:
                events.extend(entity_events)
        events.extend(e for release, e in self._delayed if release <= tick)
        self._delayed = [(release, e) for release, e in self._delayed if release > tick]
        self.state.tick = tick
        if self._recording:
            # the emission tick differs from event.tick for chaos-delayed events
            self._recording.writelines(f'{{"emitted_at":{tick},"event":{e.model_dump_json()}}}\n' for e in events)
            self._recording.flush()
        if publish:
            for event in events:
                self._publish(event)
        every = self.config.persistence.snapshot_every_ticks
        if every and tick % every == 0:
            storage.save_snapshot(self.config.simulation_id, self.snapshot())
        return events

    def advance(self, ticks: int, publish_last: bool = True) -> list[TelemetryEvent]:
        """Run `ticks` ticks at once; subscribers only see the final one (recordings get everything)."""
        events: list[TelemetryEvent] = []
        for i in range(ticks):
            events = self.step(publish=publish_last and i == ticks - 1)
        return events

    def snapshot(self) -> dict[str, Any]:
        return {
            "config": self.config.model_dump(mode="json"),
            "status": self.status,
            **self.state.snapshot(),
            "rng": _rng_state(self.rng),
            "chaos_rng": _rng_state(self.chaos_rng),
            "chaos": self.chaos.snapshot(),
            "delayed": [[release, e.model_dump(mode="json")] for release, e in self._delayed],
        }

    @classmethod
    def restore(cls, snapshot: dict[str, Any]) -> "Engine":
        """Rebuild an engine that continues exactly where the snapshot left off (status is left paused)."""
        engine = cls(SimulationConfig.model_validate(snapshot["config"]))
        engine.state.tick = snapshot["tick"]
        engine.state.entities = snapshot["entities"]
        engine.rng.setstate(_rng_from(snapshot["rng"]))
        engine.chaos_rng.setstate(_rng_from(snapshot["chaos_rng"]))
        engine.chaos.restore(snapshot["chaos"])
        engine._delayed = [(release, TelemetryEvent.model_validate(e)) for release, e in snapshot["delayed"]]
        return engine

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
        if self._recording:
            self._recording.close()
            self._recording = None
        for queue in self._subscribers:
            self._offer(queue, None)  # end-of-stream

    def inject(self, anomaly: Anomaly) -> None:
        self.chaos.inject(anomaly, self.state.tick)

    def subscribe(self) -> Subscriber:
        queue: Subscriber = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: Subscriber) -> None:
        self._subscribers.discard(queue)

    @property
    def interval_s(self) -> float:
        """Wall-clock seconds between ticks."""
        return self.config.tick_interval_ms / 1000

    async def _run(self) -> None:
        while True:
            self.step()
            await asyncio.sleep(self.interval_s)

    def _cancel(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        if not task.cancelled() and task.exception():
            log.error("simulation %s crashed", self.config.simulation_id, exc_info=task.exception())
            self.status = "failed"
            for queue in self._subscribers:
                self._offer(queue, None)

    def _publish(self, event: TelemetryEvent) -> None:
        for queue in self._subscribers:
            self._offer(queue, event)

    @staticmethod
    def _offer(queue: Subscriber, item: TelemetryEvent | None) -> None:
        # a slow client loses its oldest event rather than growing memory
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(item)


def _rng_state(rng: random.Random) -> list[Any]:
    version, internal, gauss_next = rng.getstate()
    return [version, list(internal), gauss_next]


def _rng_from(state: list[Any]) -> tuple[Any, ...]:
    return (state[0], tuple(state[1]), state[2])


simulations: dict[str, Engine] = {}
