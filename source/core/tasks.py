import asyncio
import logging

import dramatiq

logger = logging.getLogger(__name__)


async def _add(x: int, y: int) -> int:
    await asyncio.sleep(0)
    return x + y


@dramatiq.actor
def add(x: int, y: int) -> int:
    return asyncio.run(_add(x, y))


async def _log_message(message: str) -> None:
    await asyncio.sleep(0)
    logger.info("Dramatiq says: %s", message)


@dramatiq.actor
def log_message(message: str = "Hello from Dramatiq") -> None:
    asyncio.run(_log_message(message))
