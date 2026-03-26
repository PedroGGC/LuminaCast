"""
Shared persistent HTTP client.

Using a single AsyncClient with connection pooling avoids the overhead of
creating and destroying TCP connections on every request, and prevents OS-level
socket exhaustion under load.

Usage:
    from app.core.http_client import get_http_client

    client = get_http_client()
    resp = await client.get(url)
"""

import httpx

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, creating it on first call."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
        )
    return _http_client
