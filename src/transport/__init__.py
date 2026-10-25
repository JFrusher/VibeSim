from fastapi import HTTPException

from src.core.engine import Engine, simulations


def get_engine(simulation_id: str) -> Engine:
    if simulation_id not in simulations:
        raise HTTPException(404, f"simulation '{simulation_id}' not found")
    return simulations[simulation_id]
