"""Retry helper for transient API failures."""

from functools import wraps
import logging
import re
import time


def _extract_rate_limit_wait_seconds(exc: Exception) -> float | None:
    """Parse API-provided wait time from common rate-limit error text."""
    response = getattr(exc, "response", None)
    if response is None:
        return None

    status_code = getattr(response, "status_code", None)
    if status_code != 429:
        return None

    body = str(getattr(response, "text", ""))
    match = re.search(r"Please try again in (\d+)ms", body)
    if not match:
        return None

    return int(match.group(1)) / 1000.0


def retry_on_exception(retries: int = 3, exceptions=(Exception,), default_return=None):
    """Retry function calls and return a default value on final failure."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # pragma: no cover - runtime API behavior
                    logging.warning(
                        "[%s] failure (attempt %s/%s): %s",
                        func.__name__,
                        attempt,
                        retries,
                        exc,
                    )

                    # Prefer API-guided wait if available; otherwise use
                    # exponential backoff.
                    wait_seconds = _extract_rate_limit_wait_seconds(exc)
                    if wait_seconds is None:
                        wait_seconds = float(5**attempt)

                    if attempt == retries:
                        logging.error(
                            "[%s] all retries failed, returning default=%r",
                            func.__name__,
                            default_return,
                        )
                        return default_return

                    time.sleep(wait_seconds)

        return wrapper

    return decorator
