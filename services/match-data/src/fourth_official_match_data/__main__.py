"""Run the Match Data MCP server over stdio (local agents) or streamable HTTP.

    uv run python -m fourth_official_match_data
    uv run python -m fourth_official_match_data --http
    uv run python -m fourth_official_match_data --http --host 0.0.0.0 --allowed-host data.example

Over HTTP the server binds loopback by default. In a container it binds all interfaces and lists
the public host it is served under; authentication is enforced at the ingress in front of it.
"""

import argparse
from collections.abc import Sequence

from fourth_official_match_data.server import create_server
from fourth_official_match_data.store import demo_store

DEFAULT_PORT = 8100


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fourth Official Match Data MCP server")
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP, not stdio")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind for HTTP")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--allowed-host", action="append", default=[], help="public Host header to accept"
    )
    args = parser.parse_args(argv)
    server = create_server(
        demo_store(), host=args.host, port=args.port, allowed_hosts=args.allowed_host
    )
    server.run("streamable-http" if args.http else "stdio")


if __name__ == "__main__":
    main()
