"""Start the StudyRecall web app (FastAPI) pointed at a PowerContext Server.

Usage:
    python scripts/run_app.py [--port 8010] [--server-url http://127.0.0.1:8777]

Requires a PowerContext Server to already be running at --server-url
(start one with ``python scripts/run_all.py`` which launches both).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the StudyRecall app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--server-url", default=None, help="PowerContext Server base URL")
    args = parser.parse_args()

    if args.server_url:
        os.environ["STUDYRECALL_SERVER_URL"] = args.server_url

    import uvicorn

    print(f"StudyRecall UI  -> http://{args.host}:{args.port}")
    print(f"PowerContext     -> {os.environ.get('STUDYRECALL_SERVER_URL', 'http://127.0.0.1:8777')}")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
