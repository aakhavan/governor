"""Shared bits for the Streamlit pages: the token box and the API client.

The token lives in ``st.session_state["api_token"]`` (copied from the widget,
so it survives page switches). It is never logged or shown back.
"""

from __future__ import annotations

import streamlit as st

from client import ApiClient, ApiError, api_url

TOKEN = "api_token"
LOGIN_HINT = "Enter your API token in the sidebar to continue. Your role is whatever the API says the token is."


def _store_token() -> None:
    st.session_state[TOKEN] = (st.session_state.get("_token_input") or "").strip()


def token_box() -> str:
    """The sidebar token field; returns the current token ('' when none)."""
    with st.sidebar:
        st.text_input(
            "API token",
            type="password",
            key="_token_input",
            value=st.session_state.get(TOKEN, ""),
            on_change=_store_token,
            help="Bearer token issued by whoever runs the API.",
        )
        if st.session_state.get(TOKEN) and st.button("Forget token"):
            st.session_state[TOKEN] = ""
            st.session_state.pop("_token_input", None)
            st.rerun()
    return st.session_state.get(TOKEN, "")


def client(token: str = "") -> ApiClient:
    return ApiClient(api_url(), token)


def require_token() -> ApiClient | None:
    """The authenticated client, or None after showing the login hint."""
    token = token_box()
    if not token:
        st.info(LOGIN_HINT)
        return None
    return client(token)


def show_error(exc: ApiError) -> None:
    if exc.status == 401:
        st.error("The API did not accept this token.")
    else:
        st.error(f"{exc.error} ({exc.code})")


__all__ = ["ApiError", "LOGIN_HINT", "TOKEN", "client", "require_token", "show_error", "token_box"]
