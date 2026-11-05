"""The governor-ask HTTP API: every client (UI, MCP, curl) goes through these routes.

    GET  /health                           no auth: {status, as_of, version}
    POST /v1/ask                           {question, thread_id?} -> AskResult
    POST /v1/ask/certified                 {question, thread_id?} -> CertifiedAnswer (batch2b section 14)
    POST /v1/threads/{thread_id}/resume    {answer} -> AskResult
    GET  /v1/traces?outcome=&limit=        the caller's traces, newest first
    GET  /v1/traces/{trace_id}             one of the caller's traces

The caller's role comes only from the bearer token. ``GOVERNOR_API_TOKENS``
holds ``role:token,role:token``; tokens are compared with
``hmac.compare_digest`` and never logged. A role that is not in access.yaml
stops the app at startup. Request bodies forbid extra fields, so a ``role``
in the body is a 422. Every error is ``{error, code}`` JSON with no stack
trace and no echo of the request. ``GOVERNOR_LLM`` picks the chat model:
unset or ``openrouter`` = the real per-node models, ``fake`` = the offline
FakeLLM, ``fake:SCRIPT.json`` = a scripted one (demos without a key).
``/openapi.json`` is served only when ``GOVERNOR_API_DOCS=1`` (read when the
app is created); there are no /docs or /redoc pages.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

import pydantic
from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from governor.ask import certified, service
from governor.ask.policy import roles

log = logging.getLogger(__name__)

TOKENS_ENV = "GOVERNOR_API_TOKENS"
LLM_ENV = "GOVERNOR_LLM"
DOCS_ENV = "GOVERNOR_API_DOCS"
THREAD_ID = r"^[A-Za-z0-9_.:-]{1,128}$"
MAX_TEXT = 4000


class ConfigError(RuntimeError):
    """The API cannot start with this configuration."""


class ApiError(Exception):
    def __init__(self, status: int, error: str, code: str) -> None:
        super().__init__(error)
        self.status, self.error, self.code = status, error, code


# ---------------------------------------------------------------------------
# configuration


def parse_tokens(spec: str | None, known_roles: list[str]) -> list[tuple[str, str]]:
    """``role:token,role:token`` -> [(role, token)]; a malformed entry or unknown role is a ConfigError."""
    pairs = []
    for entry in (spec or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        role, sep, token = entry.partition(":")
        role, token = role.strip(), token.strip()
        if not sep or not role or not token:
            raise ConfigError(f"{TOKENS_ENV} entries must look like role:token")
        if role not in known_roles:
            raise ConfigError(f"{TOKENS_ENV} names role {role!r}, which is not in access.yaml")
        pairs.append((role, token))
    return pairs


def make_llm(spec: str | None) -> Any:
    """``GOVERNOR_LLM``: unset/``openrouter`` -> None, ``fake`` -> FakeLLM, ``fake:PATH`` -> scripted."""
    spec = (spec or "openrouter").strip()
    if spec == "openrouter":
        return None
    from governor.ask.llm_testing import FakeLLM, load_script

    if spec == "fake":
        return FakeLLM()
    if spec.startswith("fake:"):
        return load_script(spec.split(":", 1)[1])
    raise ConfigError(f"{LLM_ENV} must be openrouter, fake or fake:SCRIPT.json")


# ---------------------------------------------------------------------------
# request bodies


class AskBody(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    question: str = pydantic.Field(min_length=1, max_length=MAX_TEXT)
    thread_id: str | None = pydantic.Field(default=None, pattern=THREAD_ID)


class ResumeBody(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    answer: str = pydantic.Field(min_length=1, max_length=MAX_TEXT)


# ---------------------------------------------------------------------------
# the app


def _error(status: int, error: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "code": code})


HTTP_CODES = {401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}


def create_app(tokens: str | None = None, llm: Any = "env", **graph_options: Any) -> FastAPI:
    """Build the app. ``tokens`` defaults to ``GOVERNOR_API_TOKENS``; ``llm`` to ``GOVERNOR_LLM``."""
    known = roles(graph_options.get("access_path"))
    pairs = parse_tokens(os.environ.get(TOKENS_ENV) if tokens is None else tokens, known)
    if not pairs:
        log.warning("no API credentials configured: every /v1 request will be refused")
    llm_kind = (os.environ.get(LLM_ENV) or "openrouter") if llm == "env" else ("openrouter" if llm is None else "fake")
    if llm == "env":
        llm = make_llm(os.environ.get(LLM_ENV))
        # The certified path reads its own script key ({"certified": [...]}) from the same GOVERNOR_LLM file.
        certified_llm = certified.make_llm(os.environ.get(LLM_ENV))
    else:
        certified_llm = llm
    service.configure(llm, llm_kind=llm_kind.split(":", 1)[0], **graph_options)
    encoded = [(role, token.encode("utf-8")) for role, token in pairs]

    def caller_role(request: Request) -> str:
        scheme, _, given = (request.headers.get("authorization") or "").partition(" ")
        given = given.strip().encode("utf-8")
        if scheme.lower() != "bearer" or not given:
            raise ApiError(401, "missing bearer token", "unauthorized")
        match = None
        for role, token in encoded:  # compare against every token; no early exit
            if hmac.compare_digest(given, token):
                match = role
        if match is None:
            raise ApiError(401, "invalid token", "unauthorized")
        return match

    openapi_url = "/openapi.json" if os.environ.get(DOCS_ENV) == "1" else None
    app = FastAPI(
        title="governor-ask", version=service.version(), docs_url=None, redoc_url=None, openapi_url=openapi_url
    )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.error, exc.code)

    @app.exception_handler(service.ServiceError)
    async def _service_error(_: Request, exc: service.ServiceError) -> JSONResponse:
        status = {"not_found": 404, "thread_exists": 409, "not_waiting": 409}.get(exc.code, 400)
        return _error(status, str(exc), exc.code)

    @app.exception_handler(certified.CertifiedError)
    async def _certified_error(_: Request, exc: certified.CertifiedError) -> JSONResponse:
        return _error(503, "the certified registry is not available", "registry_unavailable")

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Name the fields only: pydantic's own message would echo the input.
        fields = sorted({".".join(str(p) for p in e.get("loc", ()) if p != "body") or "body" for e in exc.errors()})
        return _error(422, f"invalid request: {', '.join(fields)}", "invalid_request")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "not found" if exc.status_code == 404 else "request failed",
                      HTTP_CODES.get(exc.status_code, "http_error"))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled %s", type(exc).__name__)
        return _error(500, "internal error", "internal_error")

    @app.get("/health")
    def health() -> dict:
        as_of = service.as_of()
        return {"status": "ok" if as_of else "degraded", "as_of": as_of, "version": service.version()}

    @app.post("/v1/ask", response_model=service.AskResult)
    def ask(body: AskBody, role: str = Depends(caller_role)) -> service.AskResult:
        return service.ask(body.question, role, thread_id=body.thread_id)

    @app.post("/v1/ask/certified", response_model=certified.CertifiedAnswer)
    def ask_certified(body: AskBody, role: str = Depends(caller_role)) -> certified.CertifiedAnswer:
        return certified.answer(body.question, role, certified_llm, certified.default_adapter())

    @app.post("/v1/threads/{thread_id}/resume", response_model=service.AskResult)
    def resume(
        body: ResumeBody,
        thread_id: str = Path(pattern=THREAD_ID),
        role: str = Depends(caller_role),
    ) -> service.AskResult:
        return service.resume(thread_id, body.answer, role)

    @app.get("/v1/traces")
    def traces(
        outcome: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=50, ge=1, le=500),
        role: str = Depends(caller_role),
    ) -> dict:
        return {"traces": service.list_traces(role, outcome=outcome, limit=limit)}

    @app.get("/v1/traces/{trace_id}")
    def trace(trace_id: str = Path(max_length=128), role: str = Depends(caller_role)) -> dict:
        return service.get_trace(trace_id, role)

    return app


app = create_app()
