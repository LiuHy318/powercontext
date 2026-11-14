"""Runtime configuration for the StudyRecall application.

All persistent state lives in a real PowerContext Server; this module only points
the app at that Server. No application state is stored in local files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from powercontext.client import PowerContextClient

DEFAULT_SERVER_URL = "http://127.0.0.1:8777"


@dataclass(frozen=True)
class AppConfig:
    server_url: str
    request_timeout: float

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            server_url=os.environ.get("STUDYRECALL_SERVER_URL", DEFAULT_SERVER_URL).rstrip("/"),
            request_timeout=float(os.environ.get("STUDYRECALL_TIMEOUT", "20")),
        )


def create_client(config: AppConfig) -> tuple[PowerContextClient, httpx.AsyncClient]:
    """Build the PowerContext SDK client over an httpx client that bypasses env proxies.

    ``trust_env=False`` stops a Windows machine HTTP(S)_PROXY from capturing the
    loopback request to our own backend (the confirmed 502 startup failure) while
    leaving proxy behaviour for unrelated remote traffic untouched. The SDK still
    refuses a plaintext non-loopback URL, so remote http remains blocked.
    """
    http_client = httpx.AsyncClient(timeout=config.request_timeout, trust_env=False)
    client = PowerContextClient(config.server_url, http_client=http_client)
    return client, http_client


__all__ = ["AppConfig", "DEFAULT_SERVER_URL", "create_client"]
