"""Server-Sent Events stream of telemetry."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.core.engine import Engine
from src.transport import get_engine

router = APIRouter()


@router.get("/simulations/{simulation_id}/stream")
async def stream(engine: Engine = Depends(get_engine)) -> StreamingResponse:
    queue = engine.subscribe()

    async def events():
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {event.model_dump_json()}\n\n"
        finally:
            # client disconnect cancels this generator; the engine keeps ticking
            engine.unsubscribe(queue)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
