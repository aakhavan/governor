"""HTTP client for the governor API: the only way the Streamlit UI reaches governor.

``GOVERNOR_API_URL`` is the API base URL (``http://api:8000`` in compose). The
special value ``asgi`` serves the API in-process through
``httpx.ASGITransport`` (tests and single-process demos); this module is the
only place in the UI that imports ``governor.api``.

The caller's role comes from the bearer token alone; the client never sends a
role. Tokens are not logged and never appear in error messages.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

URL_ENV = "GOVERNOR_API_URL"
DEFAULT_URL = "http://localhost:8000"
ASGI = "asgi"
TIMEOUT = 120.0


class ApiError(Exception):
    """A non-2xx answer from the API: ``status``, machine ``code`` and a message safe to show."""

    def __init__(self, status: int, error: str, code: str) -> None:
        super().__init__(error)
        self.status, self.error, self.code = status, error, code


def api_url() -> str:
    return (os.environ.get(URL_ENV) or DEFAULT_URL).strip().rstrip("/")


class ApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = TIMEOUT) -> None:
        self.base_url = (base_url or api_url()).rstrip("/")
        self.token = (token or "").strip()
        self.timeout = timeout

    @property
    def in_process(self) -> bool:
        return self.base_url == ASGI

    # -- transport ----------------------------------------------------------

    def _headers(self, auth: bool) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if auth and self.token else {}

    def _request(self, method: str, path: str, *, auth: bool = True, **kwargs: Any) -> Any:
        try:
            if self.in_process:
                response = asyncio.run(self._asgi_request(method, path, headers=self._headers(auth), **kwargs))
            else:
                with httpx.Client(base_url=self.base_url, timeout=self.timeout) as http:
                    response = http.request(method, path, headers=self._headers(auth), **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(0, f"cannot reach the API ({type(exc).__name__})", "unreachable") from None
        if response.is_success:
            return response.json()
        try:
            body = response.json()
            error, code = str(body.get("error") or "request failed"), str(body.get("code") or "http_error")
        except (ValueError, AttributeError):
            error, code = "request failed", "http_error"
        raise ApiError(response.status_code, error, code)

    async def _asgi_request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        from governor.api import app as api_app  # in-process mode only

        transport = httpx.ASGITransport(app=api_app.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://governor", timeout=self.timeout) as http:
            return await http.request(method, path, **kwargs)

    # -- routes -------------------------------------------------------------

    def health(self) -> dict:
        """``GET /health`` (no token): {status, as_of, version}."""
        return self._request("GET", "/health", auth=False)

    def ask(self, question: str, thread_id: str | None = None) -> dict:
        body: dict[str, Any] = {"question": question}
        if thread_id:
            body["thread_id"] = thread_id
        return self._request("POST", "/v1/ask", json=body)

    def resume(self, thread_id: str, answer: str) -> dict:
        return self._request("POST", f"/v1/threads/{thread_id}/resume", json={"answer": answer})

    def list_traces(self, outcome: str | None = None, limit: int = 50) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if outcome:
            params["outcome"] = outcome
        return self._request("GET", "/v1/traces", params=params)["traces"]

    def get_trace(self, trace_id: str) -> dict:
        return self._request("GET", f"/v1/traces/{trace_id}")

    def list_profiles(self) -> list[str]:
        """``GET /profiles``: stored raw-profile run ids, newest first."""
        return self._request("GET", "/profiles")["profiles"]

    def get_profile(self, run_id: str) -> dict:
        """``GET /profiles/{run_id}``: one stored raw profile, unchanged."""
        return self._request("GET", f"/profiles/{run_id}")


__all__ = ["ApiClient", "ApiError", "api_url"]
