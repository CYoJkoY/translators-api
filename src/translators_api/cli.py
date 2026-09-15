from __future__ import annotations

import argparse

import uvicorn

from . import __version__
from .config import get_settings
from .main import app


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="translators-api",
        description="Run the translators-api FastAPI service.",
    )
    parser.add_argument("--host", default=settings.host, help="Bind address (default: %(default)s)")
    parser.add_argument("--port", type=int, default=settings.port, help="HTTP port (default: %(default)s)")
    parser.add_argument(
        "--log-level",
        default=settings.log_level,
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        help="Uvicorn log level (default: %(default)s)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"translators-api {__version__}",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
