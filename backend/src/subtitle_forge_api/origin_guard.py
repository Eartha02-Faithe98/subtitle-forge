"""Early browser-origin guard for local job creation requests."""

from collections.abc import Collection
from urllib.parse import urlparse

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class SubmissionOriginMiddleware:
    """Reject browser-originated cross-site job submissions before body parsing."""

    def __init__(self, app: ASGIApp, *, allowed_origins: Collection[str]) -> None:
        self._app = app
        self._allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if _is_job_creation_request(scope):
            origin = Headers(scope=scope).get("origin")
            if origin is not None and not _is_configured_origin(
                origin,
                self._allowed_origins,
            ):
                await JSONResponse(
                    status_code=403,
                    content={"detail": "This browser origin is not allowed."},
                )(scope, receive, send)
                return
        await self._app(scope, receive, send)


def _is_job_creation_request(scope: Scope) -> bool:
    request_type = scope.get("type")
    method = scope.get("method")
    path = scope.get("path")
    return (
        isinstance(request_type, str)
        and isinstance(method, str)
        and isinstance(path, str)
        and request_type == "http"
        and method == "POST"
        and path == "/api/jobs"
    )


def _is_configured_origin(value: str, allowed_origins: frozenset[str]) -> bool:
    try:
        parsed = urlparse(value)
        _port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return False
    return value.rstrip("/") in allowed_origins
