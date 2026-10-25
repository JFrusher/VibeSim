"""WebSocket: streams telemetry out, accepts anomaly injections in."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from vibesim.core.state import Anomaly
from vibesim.transport import get_engine

router = APIRouter()


@router.websocket("/simulations/{simulation_id}/ws")
async def telemetry_socket(websocket: WebSocket, simulation_id: str) -> None:
    engine = get_engine(simulation_id)
    await websocket.accept()
    queue = engine.subscribe()

    async def send_events() -> None:
        while (event := await queue.get()) is not None:
            await websocket.send_text(event.model_dump_json())
        await websocket.close()

    async def receive_chaos() -> None:
        # each inbound message is an Anomaly JSON object
        while True:
            raw = await websocket.receive_text()
            try:
                engine.inject(Anomaly.model_validate_json(raw))
            except (ValidationError, ValueError) as e:
                await websocket.send_json({"event_type": "error", "detail": str(e)})

    sender = asyncio.create_task(send_events())
    receiver = asyncio.create_task(receive_chaos())
    try:
        await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        receiver.cancel()
        engine.unsubscribe(queue)
