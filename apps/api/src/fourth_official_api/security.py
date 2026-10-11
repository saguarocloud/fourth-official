"""Browser protections on every API response.

A plain ASGI middleware, not Starlette's BaseHTTPMiddleware, so the live event streams pass through
untouched and unbuffered. JSON answers get a policy that forbids everything; the interactive API
docs load their own scripts and styles, so they keep every protection but the policy.
"""

from collections.abc import Collection

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PROTECTIONS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"strict-transport-security", b"max-age=63072000; includeSubDomains"),
    (b"cross-origin-resource-policy", b"same-origin"),
)
POLICY = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")


class SecurityHeaders:
    def __init__(self, app: ASGIApp, *, docs_paths: Collection[str] = ()) -> None:
        self._app = app
        self._docs_paths = frozenset(docs_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        path = scope["path"]
        docs = any(path == p or path.startswith(f"{p}/") for p in self._docs_paths)
        added = PROTECTIONS if docs else (*PROTECTIONS, POLICY)

        async def with_protections(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": list(message.get("headers", []))}
                headers = MutableHeaders(scope=message)
                # Set, not append: ours replace any a route set, so one value is ever sent.
                for name, value in added:
                    headers[name.decode()] = value.decode()
            await send(message)

        await self._app(scope, receive, with_protections)
