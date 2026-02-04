"""Retry logic for rate limit errors."""

import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 2.0):
    """Decorator to retry asynchronous functions on rate limit errors (e.g., 429).
    
    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds (exponential backoff).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()
                    
                    # Detect 429 or rate limit messages
                    if "429" in error_msg or "rate limit" in error_msg:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                f"Rate limit hit in {func.__name__}. "
                                f"Retrying in {delay:.1f}s (Attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                    
                    # If not a rate limit or exhausted retries, re-raise
                    raise
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator
