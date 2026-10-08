"""Launch the Project 3 V1 API."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "ma_comparable_valuation.api.app:app",
        host="127.0.0.1",
        port=8003,
        reload=False,
    )


if __name__ == "__main__":
    main()
