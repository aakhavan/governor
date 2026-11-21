"""Console routes. CORS is applied only under ``/v1/console`` so the ask routes stay closed."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from governor.core.runtrace import topology
from governor.integrations.console.artifacts import demo_file, empty, from_target
from governor.integrations.console.runs import find_run, list_runs, read_events, resolve_target, target_name, view_of
from governor.integrations.console.stream import clamp_speed, iter_frames

log = logging.getLogger(__name__)

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_PREFIX = "/v1/console"


def origins() -> set[str]:
    raw = os.environ.get("GOVERNOR_CONSOLE_ORIGINS")
    if raw is None:
        raw = _DEFAULT_ORIGINS
    return {part.strip() for part in raw.split(",") if part.strip()}


def _origin(scope: dict) -> str | None:
    for key, value in scope.get("headers") or []:
        if key == b"origin":
            text = value.decode("latin-1")
            return text if text in origins() else None
    return None


def _cors(origin: str) -> list[tuple[bytes, bytes]]:
    return [
        (b"access-control-allow-origin", origin.encode("latin-1")),
        (b"vary", b"Origin"),
        (b"access-control-allow-methods", b"GET, OPTIONS"),
        (b"access-control-allow-headers", b"Authorization, Last-Event-ID, Content-Type"),
        (b"access-control-max-age", b"600"),
    ]


class ConsoleCORS:
    """Pure ASGI middleware. ``BaseHTTPMiddleware`` would buffer the event stream."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http" or not str(scope.get("path", "")).startswith(_PREFIX):
            await self.app(scope, receive, send)
            return
        origin = _origin(scope)
        if scope.get("method") == "OPTIONS":
            headers = [(b"content-length", b"0")]
            if origin:
                headers.extend(_cors(origin))
            await send({"type": "http.response.start", "status": 204, "headers": headers})
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_cors(message: dict) -> None:
            if message["type"] == "http.response.start" and origin:
                headers = list(message.get("headers") or [])
                headers.extend(_cors(origin))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_cors)


def make_console_router(caller_role: Callable) -> APIRouter:
    """Five read-only routes. ``GOVERNOR_CONSOLE_OPEN=1`` skips the bearer token."""

    def auth(request: Request) -> str:
        if os.environ.get("GOVERNOR_CONSOLE_OPEN") == "1":
            return "open"
        return caller_role(request)

    guard = [Depends(auth)]
    router = APIRouter()

    @router.get("/graphs/{graph}", dependencies=guard)
    def graph_topology(graph: str) -> dict:
        if graph not in ("build", "ask"):
            raise HTTPException(404)
        try:
            return topology(graph)
        except KeyError:
            raise HTTPException(404) from None

    @router.get("/runs", dependencies=guard)
    def runs(
        graph: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict:
        if graph not in (None, "", "build", "ask"):
            return {"runs": []}
        return {"runs": list_runs(graph or None, limit)}

    @router.get("/runs/{run_id}", dependencies=guard)
    def run_view(run_id: str) -> dict:
        found = find_run(run_id)
        if found is None:
            raise HTTPException(404)
        _, _, path = found
        return view_of(read_events(path))

    @router.get("/runs/{run_id}/events", dependencies=guard)
    def run_events(
        run_id: str,
        replay: int = Query(default=0),
        speed: float = Query(default=4),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        found = find_run(run_id)
        if found is None:
            raise HTTPException(404)
        _, _, path = found
        last = int(last_event_id) if last_event_id and last_event_id.strip().isdigit() else 0

        def frames():
            try:
                yield from iter_frames(path, replay=replay == 1, speed=clamp_speed(speed), last_id=last)
            except Exception as exc:  # noqa: BLE001 — a stream error must not echo a path or a value
                log.warning("console stream failed: %s", type(exc).__name__)

        return StreamingResponse(frames(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    @router.get("/runs/{run_id}/artifacts", dependencies=guard)
    def run_artifacts(run_id: str) -> dict:
        found = find_run(run_id)
        if found is None:
            raise HTTPException(404)
        source, graph, path = found
        if source == "demo":
            return demo_file(run_id) or empty()
        if graph != "build":
            return empty()
        folder = resolve_target(target_name(read_events(path)))
        if folder is None:
            return empty()
        return from_target(folder)

    return router


def mount_console(app: FastAPI, caller_role: Callable) -> None:
    """Mount the router at ``/v1/console`` and the console-only CORS middleware."""
    app.include_router(make_console_router(caller_role), prefix=_PREFIX)
    app.add_middleware(ConsoleCORS)
