"""Local developer command for serving the Project 1 FastAPI application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="madi-api", description="Serve the local Project 1 API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.port <= 65_535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(
        "ma_company_intelligence.api:app",
        host=arguments.host,
        port=arguments.port,
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
