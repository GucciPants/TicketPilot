"""Async base agent using Redis Streams for event-driven pipeline execution."""
import os
import json
import asyncio
import logging
import time
from typing import Optional
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)


class AsyncBaseAgent:
    """Base class for async agents that consume/produce Redis Stream events.

    Each agent subscribes to an input stream, processes messages concurrently
    up to max_concurrency, and publishes results to an output stream.
    """

    def __init__(self, input_stream: str, output_stream: str,
                 concurrency: int = None, batch_size: int = 1):
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.concurrency = concurrency or int(os.getenv("WORKER_CONCURRENCY", "2"))
        self.batch_size = batch_size
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._redis = None
        self._running = False
        self._last_id = "$"  # Stream cursor: tracks last read position

    async def _get_redis(self):
        """Lazy-init Redis connection."""
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379/0")
            )
        return self._redis

    async def process_message(self, message: dict) -> dict:
        """Process a single message. Override in subclass."""
        raise NotImplementedError

    @async_retry(max_retries=3, base_delay=1.0, backoff=2.0)
    async def _process_with_semaphore(self, message: dict) -> Optional[dict]:
        """Process with concurrency control."""
        async with self._semaphore:
            start = time.time()
            try:
                result = await self.process_message(message)
                elapsed = time.time() - start
                logger.debug(
                    "Processed %s in %.2fs (concurrent: %d/%d)",
                    self.input_stream, elapsed,
                    self.concurrency - self._semaphore._value,
                    self.concurrency
                )
                return result
            except Exception as e:
                logger.error("Failed to process message: %s", e)
                return None

    async def publish_result(self, stream: str, data: dict):
        """Publish result to a Redis Stream."""
        r = await self._get_redis()
        await r.xadd(stream, {"data": json.dumps(data)}, maxlen=10000)

    async def publish_event(self, channel: str, data: dict):
        """Publish a JSON message to a Redis Pub/Sub channel (used for SSE)."""
        r = await self._get_redis()
        await r.publish(channel, json.dumps(data))

    async def run(self):
        """Main loop: consume from input stream, process, publish to output."""
        r = await self._get_redis()
        self._running = True
        logger.info(
            "Starting %s: %s → %s (concurrency=%d)",
            self.__class__.__name__,
            self.input_stream, self.output_stream,
            self.concurrency
        )

        while self._running:
            try:
                results = await r.xread(
                    {self.input_stream: self._last_id},
                    count=self.batch_size,
                    block=5000
                )
                if not results:
                    continue

                tasks = []
                for stream_name, messages in results:
                    for msg_id, msg_data in messages:
                        # Track the last read message ID for next iteration
                        self._last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
                        try:
                            payload = json.loads(msg_data[b"data"].decode())
                            tasks.append(self._process_with_semaphore(payload))
                        except Exception as e:
                            logger.warning("Invalid message: %s", e)

                if tasks:
                    outputs = await asyncio.gather(*tasks, return_exceptions=True)
                    for output in outputs:
                        if output and not isinstance(output, Exception):
                            await self.publish_result(self.output_stream, output)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Stream read error: %s", e)
                await asyncio.sleep(2)

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        if self._redis:
            await self._redis.close()
