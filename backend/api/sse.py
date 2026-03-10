"""
Server-Sent Events log stream.

Clients subscribe to GET /tasks/{id}/stream and receive log lines as they are
produced by the orchestrator. Uses an asyncio.Queue per task.
"""

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# task_id → asyncio.Queue of log line strings
_queues: dict[str, asyncio.Queue] = {}


def get_or_create_queue(task_id: str) -> asyncio.Queue:
    if task_id not in _queues:
        _queues[task_id] = asyncio.Queue()
    return _queues[task_id]


def publish_log(task_id: str, message: str) -> None:
    """Push a log line to the SSE queue for the given task."""
    queue = get_or_create_queue(task_id)
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        logger.warning("SSE queue full for task %s, dropping log line.", task_id)


async def _event_generator(task_id: str) -> AsyncIterator[str]:
    queue = get_or_create_queue(task_id)
    while True:
        try:
            message = await asyncio.wait_for(queue.get(), timeout=30.0)
            if message is None:  # sentinel: stream closed
                yield "event: done\ndata: {}\n\n"
                break
            payload = json.dumps({"message": message})
            yield f"data: {payload}\n\n"
        except asyncio.TimeoutError:
            # Keep-alive comment to prevent connection timeout
            yield ": keep-alive\n\n"


def make_sse_response(task_id: str) -> StreamingResponse:
    return StreamingResponse(
        _event_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def close_stream(task_id: str) -> None:
    """Signal that the SSE stream for this task is done."""
    queue = get_or_create_queue(task_id)
    queue.put_nowait(None)
