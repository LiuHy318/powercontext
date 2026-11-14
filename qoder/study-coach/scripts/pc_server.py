"""Lifecycle helper for running a real PowerContext Server with isolated storage.

Used by the integration tests and by ``scripts/run_all.py`` so the demo and the
tests exercise the same genuine PowerContext backend (SQLite persistence under a
dedicated ``POWERCONTEXT_HOME``), never a fake in-memory stand-in.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import IO

import httpx

_LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")


def _with_loopback_no_proxy(env: dict[str, str]) -> dict[str, str]:
    """Append loopback hosts to NO_PROXY without touching unrelated proxy routing.

    Windows dev machines often set a system HTTP(S)_PROXY. If NO_PROXY omits
    loopback, a request to our own freshly-spawned 127.0.0.1 server is sent to the
    corporate proxy and fails (502). We add the loopback entries to the existing
    value, preserving every prior exclusion and leaving remote proxying intact.
    """
    out = dict(env)
    for key in ("NO_PROXY", "no_proxy"):
        current = out.get(key, "")
        entries = [item.strip() for item in current.split(",") if item.strip()]
        for host in _LOOPBACK_NO_PROXY:
            if host not in entries:
                entries.append(host)
        out[key] = ",".join(entries)
    return out


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class PowerContextServer:
    """Own one ``powercontext server run`` subprocess bound to an isolated data dir."""

    def __init__(self, data_dir: Path, port: int | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.port = port or free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._proc: subprocess.Popen[bytes] | None = None
        self._log: IO[str] | None = None
        self.log_path = self.data_dir / "server.log"

    def start(self, timeout: float = 90.0) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        env = _with_loopback_no_proxy(dict(os.environ))
        env["POWERCONTEXT_HOME"] = str(self.data_dir)
        self._log = self.log_path.open("w", encoding="utf-8")  # noqa: SIM115
        launcher = (
            "import sys;"
            "from powercontext.cli.app import main;"
            "sys.argv=['powercontext']+sys.argv[1:];"
            "main()"
        )
        self._proc = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-c",
                launcher,
                "server",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--no-env-file",
            ],
            stdout=self._log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        try:
            self._wait_ready(timeout)
        except Exception:
            # Never leave an orphan server running when startup fails.
            self.stop()
            raise

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.time() + timeout
        last_error: str = ""
        while time.time() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise RuntimeError(f"PowerContext Server exited early (code {self._proc.returncode}); see {self.log_path}")
            try:
                # trust_env=False: reach our own loopback server directly, never via
                # a machine proxy, without changing proxy behaviour for other traffic.
                resp = httpx.get(f"{self.base_url}/health/ready", timeout=2.0, trust_env=False)
                if resp.status_code == 200:
                    return
                last_error = f"HTTP {resp.status_code}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            time.sleep(1.0)
        raise RuntimeError(f"PowerContext Server not ready within {timeout}s ({last_error}); see {self.log_path}")

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=10)
            self._proc = None
        if self._log is not None:
            self._log.close()
            self._log = None

    def restart(self) -> None:
        """Stop the process and start a fresh one on the same data dir (restart recovery)."""
        self.stop()
        self.start()

    def __enter__(self) -> "PowerContextServer":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


__all__ = ["PowerContextServer", "free_port"]
