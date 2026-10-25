"""REST control plane. Run with: python -m vibesim"""

import asyncio
from typing import Any, Literal, Self

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from vibesim.chaos.compiler import compile_chaos_with
from vibesim.core.compiler import Compiler, compile_with
from vibesim.core.engine import Engine, simulations
from vibesim.core.state import Anomaly, SimulationConfig
from vibesim.transport import EngineDep, sse, websocket

app = FastAPI(title="VibeSim")
app.include_router(sse.router)
app.include_router(websocket.router)


class CompileRequest(BaseModel):
    prompt: str
    compiler: Compiler = "keyword"
    seed: int = 0


class ChaosPrompt(BaseModel):
    prompt: str
    compiler: Compiler = "keyword"


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


@app.get("/simulations/{simulation_id}/state")
async def get_state(engine: EngineDep) -> dict[str, Any]:
    return describe(engine)


@app.delete("/simulations/{simulation_id}", status_code=204)
async def delete_simulation(engine: EngineDep) -> None:
    engine.stop()
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
