"""
Shared HTTP Client with Connection Pooling
Reuses TCP connections across requests to avoid the overhead of creating
a new connection for every external API call (OpenAI, GPTZero, stylometry, etc.).
"""

import httpx
import logging

logger = logging.getLogger(__name__)

from typing import Optional

# Shared client instance (initialized during app startup, closed on shutdown)
_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """Get the shared async HTTP client. Creates one lazily if not yet initialized."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            ),
            follow_redirects=True,
        )
        logger.info("Created shared httpx.AsyncClient with connection pooling")
    return _client


async def close_client():
    """Close the shared client. Call during app shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        logger.info("Closed shared httpx.AsyncClient")
