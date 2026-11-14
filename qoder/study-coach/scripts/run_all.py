"""Launch BOTH a real PowerContext Server (isolated local storage) and the app.

This is the one-command way to run the full application for review:
    python scripts/run_all.py [--app-port 8010]

The PowerContext Server persists to ``.runtime/demo`` (created on demand, ignored
by git). Nothing here uses a fake store; the app talks to the real Server over HTTP.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pc_server import PowerContextServer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PowerContext Server + StudyRecall app together")
    parser.add_argument("--app-host", default="127.0.0.1")
    parser.add_argument("--app-port", type=int, default=8010)
    parser.add_argument("--pc-port", type=int, default=None, help="PowerContext Server port (default: auto)")
    args = parser.parse_args()

    server = PowerContextServer(PROJECT_ROOT / ".runtime" / "demo", port=args.pc_port)
    print("Starting PowerContext Server (isolated storage under .runtime/demo) …")
    server.start()
    print(f"PowerContext Server ready -> {server.base_url}")
    try:
        import os

        os.environ["STUDYRECALL_SERVER_URL"] = server.base_url
        import uvicorn

        print(f"StudyRecall UI -> http://{args.app_host}:{args.app_port}")
        print(f"打开后点击“载入合成示例”即可用合成学习者数据体验完整流程。")
        uvicorn.run("app.main:app", host=args.app_host, port=args.app_port, reload=False)
    finally:
        print("\nStopping PowerContext Server …")
        server.stop()


if __name__ == "__main__":
    main()
