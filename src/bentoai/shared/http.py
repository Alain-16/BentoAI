from functools import lru_cache

import httpx


@lru_cache
def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )