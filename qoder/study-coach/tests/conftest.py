"""Shared pytest fixtures: boot a real PowerContext Server once per test session.

The tests talk to an actual PowerContext Server (isolated SQLite storage under
``.runtime/testdata``) through the same application code path a user hits, so a
green run is evidence of genuine PowerContext persistence, not a mock.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import create_app  # noqa: E402
from scripts.pc_server import PowerContextServer  # noqa: E402


@pytest.fixture(scope="session")
def pc_server() -> PowerContextServer:
    server = PowerContextServer(PROJECT_ROOT / ".runtime" / "testdata")
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def client(pc_server: PowerContextServer):
    app = create_app(pc_server.base_url)
    with TestClient(app) as test_client:
        yield test_client


def unique(title: str) -> str:
    import uuid

    return f"{title}-{uuid.uuid4().hex[:8]}"
