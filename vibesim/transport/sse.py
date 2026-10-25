"""Server-Sent Events stream of telemetry."""

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from vibesim.transport import EngineDep

router = APIRouter()


@router.get("/simulations/{simulation_id}/stream")
async def stream(engine: EngineDep) -> StreamingResponse:
    queue = engine.subscribe()

    async def events() -> AsyncIterator[str]:
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {event.model_dump_json()}\n\n"
        finally:
            # client disconnect cancels this generator; the engine keeps ticking
            engine.unsubscribe(queue)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
