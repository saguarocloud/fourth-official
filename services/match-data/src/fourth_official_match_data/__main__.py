"""Run the Match Data MCP server over streamable HTTP (or stdio for local agents).

uv run python -m fourth_official_match_data            # stdio, for a local agent
uv run python -m fourth_official_match_data --http     # streamable HTTP on 127.0.0.1:8100
"""

import argparse
from collections.abc import Sequence

from fourth_official_match_data.server import create_server
from fourth_official_match_data.store import demo_store

DEFAULT_PORT = 8100


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fourth Official Match Data MCP server")
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP, not stdio")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    server = create_server(demo_store())
    if args.http:
        # Loopback only: inside a container, the platform's ingress is the only way in.
        server.settings.host = "127.0.0.1"
        server.settings.port = args.port
        server.run("streamable-http")
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
