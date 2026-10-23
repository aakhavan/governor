"""Ask a question; answer card, clarify flow and refusals. Talks to the API only.

Session state: ``thread_id`` and ``clarify_question`` while a clarification is
pending, ``ask_result`` for the last result. The API is called only when a form
is submitted, so a rerun never starts a new ask or drops a pending thread.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import ApiError, require_token, show_error  # noqa: E402

STATUS_LABEL = {
    "answered": "Answered",
    "refused": "Refused",
    "unanswerable": "Cannot answer",
    "error": "Could not answer",
}


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for name in names:
        n = seen.get(name, 0)
        seen[name] = n + 1
        out.append(name if n == 0 else f"{name}_{n + 1}")
    return out


def _cost(value: float | None) -> str:
    return "cost unknown" if value is None else f"${value:.4f}"


def show_result(result: dict) -> None:
    status = result.get("status")
    with st.container(border=True):
        top = st.columns([3, 1])
        top[0].markdown(f"**{STATUS_LABEL.get(status, status)}**")
        with top[1]:
            st.badge(_cost(result.get("cost_usd")), icon=":material/payments:", color="gray")
        text = result.get("answer") or ""
        if status == "answered":
            st.markdown(text)
        elif status == "refused":
            st.error(text or "This question was refused.", icon=":material/block:")
        else:
            st.warning(text or "No answer.")

        columns, rows = result.get("result_columns") or [], result.get("result_rows") or []
        if columns:
            st.dataframe([dict(zip(_unique(columns), row)) for row in rows], hide_index=True, width="stretch")
            st.caption(f"{len(rows)} row(s)")
        if result.get("sql"):
            with st.expander("SQL"):
                st.code(result["sql"], language="sql")
        if result.get("models"):
            st.markdown("**Models:** " + ", ".join(f"`{m}`" for m in result["models"]))
        if result.get("lineage"):
            st.markdown("**Upstream sources:** " + ", ".join(f"`{s}`" for s in result["lineage"]))
        if result.get("freshness"):
            with st.expander("Freshness"):
                st.dataframe(result["freshness"], hide_index=True, width="stretch")
        if result.get("trace_id"):
            st.caption(f"Trace `{result['trace_id']}`")


def clear_pending() -> None:
    st.session_state.pop("thread_id", None)
    st.session_state.pop("clarify_question", None)


def keep(result: dict) -> None:
    """Store a result; a clarify keeps its thread for the reply box."""
    st.session_state["ask_result"] = result
    if result.get("status") == "clarify":
        st.session_state["thread_id"] = result["thread_id"]
        st.session_state["clarify_question"] = result.get("clarify_question") or "Can you say more?"
    else:
        clear_pending()


st.title("Ask")
api = require_token()
if api is None:
    st.stop()

if st.session_state.get("ask_error"):
    show_error(st.session_state.pop("ask_error"))

if st.session_state.get("thread_id"):
    st.info(st.session_state.get("clarify_question"), icon=":material/help:")
    with st.form("clarify", clear_on_submit=True):
        reply = st.text_input("Your reply")
        sent = st.form_submit_button("Send reply")
    if sent and reply.strip():
        try:
            with st.spinner("Thinking..."):
                keep(api.resume(st.session_state["thread_id"], reply.strip()))
        except ApiError as exc:
            if exc.status in (404, 409):  # gone or no longer waiting: start over
                clear_pending()
                st.session_state.pop("ask_result", None)
            st.session_state["ask_error"] = exc
        st.rerun()
    if st.button("Drop this question"):
        clear_pending()
        st.session_state.pop("ask_result", None)
        st.rerun()
else:
    with st.form("ask"):
        question = st.text_area("Question", placeholder="Ask about accounts, invoices, payments...")
        asked = st.form_submit_button("Ask")
    if asked and question.strip():
        try:
            with st.spinner("Thinking..."):
                keep(api.ask(question.strip()))
        except ApiError as exc:
            show_error(exc)
        else:
            st.rerun()

result = st.session_state.get("ask_result")
if result and result.get("status") != "clarify":
    show_result(result)
