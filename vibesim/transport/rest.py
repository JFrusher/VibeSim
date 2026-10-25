"""REST control plane. Run with: python -m vibesim"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal, Self

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, model_validator

from vibesim import storage
from vibesim.chaos.compiler import compile_chaos_with
from vibesim.core.compiler import Compiler, compile_with
from vibesim.core.engine import Engine, simulations
from vibesim.core.state import Anomaly, SimulationConfig
from vibesim.replay import ReplayEngine
from vibesim.scenario import dump_scenario
from vibesim.transport import EngineDep, sse, websocket

log = logging.getLogger(__name__)
ADVANCE_CHUNK = 1000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Resume simulations that were snapshotting when the server last stopped."""
    for snapshot in storage.load_snapshots():
        if snapshot["status"] in ("stopped", "failed"):
            continue
        engine = Engine.restore(snapshot)
        simulations[engine.config.simulation_id] = engine
        if snapshot["status"] == "running":
            engine.start()
        log.info("resumed %s at tick %d", engine.config.simulation_id, engine.state.tick)
    yield


app = FastAPI(title="VibeSim", lifespan=lifespan)
app.include_router(sse.router)
app.include_router(websocket.router)


class CompileRequest(BaseModel):
    prompt: str
    compiler: Compiler = "keyword"
    seed: int = 0


class ChaosPrompt(BaseModel):
    prompt: str
    compiler: Compiler = "keyword"


class CreateReplay(BaseModel):
    recording_id: str
    speed: float = Field(1.0, gt=0.0)


class CreateSimulation(BaseModel):
    """Exactly one of `prompt` or `config`."""

    prompt: str | None = None
    config: SimulationConfig | None = None
    compiler: Compiler = "keyword"
    seed: int = 0

    @model_validator(mode="after")
    def one_source(self) -> Self:
        if (self.prompt is None) == (self.config is None):
            raise ValueError("provide exactly one of 'prompt' or 'config'")
        return self


def describe(engine: Engine) -> dict[str, Any]:
    return {
        "simulation_id": engine.config.simulation_id,
        "status": engine.status,
        **engine.state.snapshot(),
        "active_anomalies": [a.model_dump() for a in engine.chaos.anomalies],
    }


@app.post("/compile")
async def compile_only(body: CompileRequest) -> SimulationConfig:
    """Return the config a prompt compiles to, without running it."""
    try:
        return await asyncio.to_thread(compile_with, body.compiler, body.prompt, body.seed)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/simulations", status_code=201)
async def create_simulation(body: CreateSimulation) -> dict[str, Any]:
    try:
        # compiling may call OSRM or Claude; a thread keeps other simulations ticking meanwhile
        config = body.config
        if config is None:
            config = await asyncio.to_thread(compile_with, body.compiler, str(body.prompt), body.seed)
        engine = Engine(config)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if config.simulation_id in simulations:
        raise HTTPException(409, f"simulation '{config.simulation_id}' already exists")
    simulations[config.simulation_id] = engine
    engine.start()
    return {**describe(engine), "config": config.model_dump()}


@app.get("/simulations")
async def list_simulations() -> list[dict[str, Any]]:
    return [
        {"simulation_id": sid, "domain": e.config.domain, "status": e.status, "tick": e.state.tick}
        for sid, e in simulations.items()
    ]


@app.get("/simulations/{simulation_id}/scenario")
async def export_scenario(engine: EngineDep, format: Literal["yaml", "json"] = "yaml") -> PlainTextResponse:
    media = "application/yaml" if format == "yaml" else "application/json"
    return PlainTextResponse(dump_scenario(engine.config, format), media_type=media)


@app.post("/simulations/{simulation_id}/advance")
async def advance(engine: EngineDep, ticks: Annotated[int, Query(ge=1, le=1_000_000)]) -> dict[str, Any]:
    """Fast-forward: run `ticks` ticks now. Subscribers receive only the final tick."""
    remaining = ticks
    try:
        while remaining:
            chunk = min(ADVANCE_CHUNK, remaining)
            remaining -= chunk
            engine.advance(chunk, publish_last=remaining == 0)
            await asyncio.sleep(0)  # let other simulations and streams run between chunks
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return describe(engine)


@app.get("/recordings")
async def list_recordings() -> list[str]:
    return storage.list_recordings()


@app.post("/replays", status_code=201)
async def create_replay(body: CreateReplay) -> dict[str, Any]:
    try:
        engine = ReplayEngine(body.recording_id, body.speed)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    simulations[engine.config.simulation_id] = engine
    engine.start()
    return describe(engine)


@app.get("/simulations/{simulation_id}/state")
async def get_state(engine: EngineDep) -> dict[str, Any]:
    return describe(engine)


@app.delete("/simulations/{simulation_id}", status_code=204)
async def delete_simulation(engine: EngineDep) -> None:
    engine.stop()
    storage.delete_snapshot(engine.config.simulation_id)
    del simulations[engine.config.simulation_id]


@app.post("/simulations/{simulation_id}/chaos", status_code=201)
async def inject_chaos(anomaly: Anomaly, engine: EngineDep) -> dict[str, Any]:
    try:
        engine.inject(anomaly)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return describe(engine)


@app.post("/simulations/{simulation_id}/chaos/prompt", status_code=201)
async def inject_chaos_prompt(body: ChaosPrompt, engine: EngineDep) -> dict[str, Any]:
    """Compile a plain-English failure into an anomaly and inject it."""
    try:
        anomaly = await asyncio.to_thread(
            compile_chaos_with,
            body.compiler,
            body.prompt,
            engine.state.snapshot()["entities"],
            engine.config.tick_interval_ms,
        )
        engine.inject(anomaly)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {**describe(engine), "injected": anomaly.model_dump()}


@app.delete("/simulations/{simulation_id}/chaos/{name}")
async def remove_chaos(name: str, engine: EngineDep) -> dict[str, Any]:
    try:
        engine.chaos.remove(name)
    except KeyError:
        raise HTTPException(404, f"anomaly '{name}' not active") from None
    return describe(engine)


# declared last so the literal /chaos route above wins the match
@app.post("/simulations/{simulation_id}/{action}")
async def control(action: Literal["start", "pause", "step", "stop"], engine: EngineDep) -> dict[str, Any]:
    try:
        getattr(engine, action)()
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return describe(engine)
