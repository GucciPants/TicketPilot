"""Universal retry decorator with exponential backoff for sync and async functions."""
import asyncio
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def sync_retry(max_retries: int = 3, base_delay: float = 1.0, backoff: float = 2.0,
               exceptions: tuple = (Exception,)):
    """Retry a synchronous function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before the first retry.
        backoff: Multiplier applied to the delay after each retry.
        exceptions: Tuple of exception types that trigger a retry.

    Returns:
        The decorated function's result.

    Raises:
        The last exception encountered if all retries are exhausted.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.1fs...",
                        func.__name__, attempt, max_retries, e, delay
                    )
                    time.sleep(delay)
                    delay *= backoff
            logger.error("%s failed after %d retries", func.__name__, max_retries)
            raise last_exc
        return wrapper
    return decorator


def async_retry(max_retries: int = 3, base_delay: float = 1.0, backoff: float = 2.0,
                exceptions: tuple = (Exception,)):
    """Retry an async function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before the first retry.
        backoff: Multiplier applied to the delay after each retry.
        exceptions: Tuple of exception types that trigger a retry.

    Returns:
        The decorated function's result.

    Raises:
        The last exception encountered if all retries are exhausted.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.1fs...",
                        func.__name__, attempt, max_retries, e, delay
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
            logger.error("%s failed after %d retries", func.__name__, max_retries)
            raise last_exc
        return wrapper
    return decorator
