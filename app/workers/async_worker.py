"""Async worker - runs the event-driven agent pipeline using Redis Streams."""
import os
import asyncio
import logging
from app.agents.async_base import AsyncBaseAgent
from app.agents.async_persistence import PersistenceAgent

logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()))
logger = logging.getLogger("async_worker")


async def main():
    """Start all async pipeline agents."""
    from app.agents.async_agents import (
        AsyncRouterAgent,
        AsyncContextAgent,
        AsyncResolverAgent,
        AsyncQualityAgent,
    )

    agents = [
        AsyncRouterAgent(),
        AsyncContextAgent(),
        AsyncResolverAgent(),
        AsyncQualityAgent(),
        PersistenceAgent(),
    ]

    logger.info("Starting %d async pipeline agents...", len(agents))
    for a in agents:
        logger.info("  %s: %s → %s (concurrency=%d)",
                    a.__class__.__name__, a.input_stream, a.output_stream, a.concurrency)

    try:
        await asyncio.gather(*(a.run() for a in agents))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for a in agents:
            await a.stop()


if __name__ == "__main__":
    asyncio.run(main())
