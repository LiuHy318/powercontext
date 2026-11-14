"""Client-transport security guard, verified WITHOUT any network request.

These assert the SDK behaviour that ``create_client`` relies on: a plaintext
non-loopback URL is rejected during construction (before touching the socket),
while loopback and HTTPS are accepted. Nothing here connects to a server.
"""

from __future__ import annotations

import asyncio

import pytest

from app.config import AppConfig, create_client


def test_rejects_remote_plaintext_http_without_network() -> None:
    # 203.0.113.0/24 is TEST-NET-3 (RFC 5737) and is never contacted: the SDK guard
    # raises while building the client, before any request would be made.
    with pytest.raises(ValueError, match="non-loopback HTTP"):
        create_client(AppConfig(server_url="http://203.0.113.10:8777", request_timeout=5))


def test_allows_loopback_http_and_remote_https() -> None:
    async def _exercise() -> None:
        built = []
        for url in (
            "http://127.0.0.1:8777",
            "http://localhost:9000",
            "https://powercontext.example.com",
        ):
            client, http = create_client(AppConfig(server_url=url, request_timeout=5))
            assert http.trust_env is False  # env-proxy bypass for the loopback backend
            built.append(http)
        for http in built:
            await http.aclose()

    asyncio.run(_exercise())
