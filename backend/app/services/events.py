"""Live events for the authority dashboard.

publish(event) can be called from any request. Every connected dashboard WebSocket has its
own queue; the event is copied into every queue ("fan-out").

Two transports, chosen at startup (settings.event_backend):
- redis : publish goes to a Redis channel; a background listener receives it and fans out.
          With several API processes, all of them see every event.
- memory: publish fans out directly inside this one process (no Redis needed for demos).
"""

import asyncio
import json
import logging

import redis
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "tsmirp:dashboard"
QUEUE_SIZE = 100  # per dashboard connection; a stuck client loses old events, not the API


class EventBus:
    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self.mode = "memory"
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._redis_sync: redis.Redis | None = None
        self._redis_async: aioredis.Redis | None = None
        self._listener: asyncio.Task | None = None

    async def start(self) -> None:
        """Called once when the API starts (see app/main.py)."""
        self._loop = asyncio.get_running_loop()
        self.mode = "memory"
        if settings.event_backend in ("auto", "redis"):
            try:
                await self._connect_redis()
                self.mode = "redis"
            except (redis.RedisError, OSError):
                if settings.event_backend == "redis":
                    raise
                logger.warning("Redis not reachable: dashboard events stay inside this process")
        logger.info("Dashboard event backend: %s", self.mode)

    async def _connect_redis(self) -> None:
        client = aioredis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        await client.ping()
        pubsub = client.pubsub()
        await pubsub.subscribe(CHANNEL)  # subscribed before start() returns: no events missed
        self._redis_async = client
        self._redis_sync = redis.Redis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        self._listener = asyncio.create_task(self._listen(pubsub))

    async def _listen(self, pubsub) -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                self._fan_out(json.loads(message["data"]))

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
        if self._redis_async is not None:
            await self._redis_async.aclose()
        if self._redis_sync is not None:
            self._redis_sync.close()
        self._reset()

    def publish(self, event: dict) -> None:
        """Send an event to every dashboard. Safe to call from normal (non-async) routes."""
        if self.mode == "redis" and self._redis_sync is not None:
            try:
                self._redis_sync.publish(CHANNEL, json.dumps(event))
                return
            except redis.RedisError:
                logger.warning("Redis publish failed; delivering inside this process instead")
        if self._loop is not None:
            # Routes run in worker threads; hand the work to the event loop thread safely.
            self._loop.call_soon_threadsafe(self._fan_out, event)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def _fan_out(self, event: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dashboard client too slow; dropping an event for it")


event_bus = EventBus()
