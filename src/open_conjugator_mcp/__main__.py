from __future__ import annotations

import argparse

from .config import settings
from .server import server


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Conjugator MCP")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    args = parser.parse_args()
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(
            transport="streamable-http",
            host=settings.host,
            port=settings.port,
            streamable_http_path=settings.mcp_path,
            stateless_http=True,
            json_response=True,
            max_request_body_size=256 * 1024,
            max_sessions=500,
        )


if __name__ == "__main__":
    main()

