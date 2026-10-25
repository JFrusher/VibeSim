"""REST control plane. Run with: uvicorn vibesim.transport.rest:app"""

from typing import Any, Literal, Self

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator

from vibesim.core.compiler import compile_prompt
from vibesim.core.engine import Engine, simulations
from vibesim.core.state import Anomaly, SimulationConfig
from vibesim.transport import EngineDep, sse, websocket

app = FastAPI(title="VibeSim")
app.include_router(sse.router)
app.include_router(websocket.router)


class CreateSimulation(BaseModel):
    """Exactly one of `prompt` or `config`."""

    prompt: str | None = None
    config: SimulationConfig | None = None
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


@app.post("/simulations", status_code=201)
async def create_simulation(body: CreateSimulation) -> dict[str, Any]:
    try:
        config = body.config if body.config is not None else compile_prompt(str(body.prompt), seed=body.seed)
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
