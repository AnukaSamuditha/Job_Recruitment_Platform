"""In-process pub/sub for screening WebSocket clients (per run id)."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class ScreeningBroadcaster:
    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._queues[run_id].append(q)
        logger.debug("WS subscribe run_id=%s (subscribers=%s)", run_id, len(self._queues[run_id]))
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._queues.get(run_id)
        if not subs:
            return
        if q in subs:
            subs.remove(q)
        if not subs:
            del self._queues[run_id]

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        for q in list(self._queues.get(run_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("WS queue full for run_id=%s", run_id)
