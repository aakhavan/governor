"""The caller's decision traces: filter by outcome, list, and inspect one. Talks to the API only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import ApiError, require_token, show_error  # noqa: E402

ALL = "(all)"
OUTCOMES = [ALL, "answer", "refused_guard", "refused_policy", "refused_repair", "refused_error",
            "unanswerable", "clarify_failed"]
LIST_COLUMNS = ["ts", "outcome", "row_count", "cost_usd", "latency_s", "models", "trace_id"]

st.title("Trace explorer")
api = require_token()
if api is None:
    st.stop()

top = st.columns([2, 1])
outcome = top[0].selectbox("Outcome", OUTCOMES)
limit = top[1].number_input("Rows", min_value=1, max_value=500, value=50)
try:
    rows = api.list_traces(outcome=None if outcome == ALL else outcome, limit=int(limit))
except ApiError as exc:
    show_error(exc)
    st.stop()

if not rows:
    st.info("No traces yet. Ask a question first.")
    st.stop()

table = [{c: (", ".join(r.get(c) or []) if c == "models" else r.get(c)) for c in LIST_COLUMNS} for r in rows]
st.dataframe(table, hide_index=True, width="stretch")
st.caption(f"{len(rows)} trace(s), newest first")

st.subheader("Trace detail")
trace_ids = [r["trace_id"] for r in rows]
labels = {r["trace_id"]: f"{(r.get('ts') or '')[:19]}  {r.get('outcome')}  {r['trace_id'][:8]}" for r in rows}
chosen = st.selectbox("Trace", trace_ids, format_func=labels.get)
try:
    trace = api.get_trace(chosen)
except ApiError as exc:
    show_error(exc)
    st.stop()

cols = st.columns(4)
cols[0].metric("Outcome", trace.get("outcome") or "?")
cols[1].metric("Rows", trace.get("row_count") or 0)
cols[2].metric("Cost", "?" if trace.get("cost_usd") is None else f"${trace['cost_usd']:.4f}")
cols[3].metric("Latency", "?" if trace.get("latency_s") is None else f"{trace['latency_s']:.2f} s")
if trace.get("answer"):
    st.markdown(f"**Answer:** {trace['answer']}")
st.caption("LLM models: " + (", ".join(trace.get("models") or []) or "none"))

st.markdown("**Plan**")
plan = trace.get("plan_json")
if plan:
    try:
        st.json(json.loads(plan))
    except ValueError:
        st.code(plan)
else:
    st.caption("No plan recorded.")

st.markdown("**SQL attempts**")
attempts = trace.get("sql_attempts") or []
if not attempts:
    st.caption("No SQL was drafted.")
for i, attempt in enumerate(attempts, 1):
    codes = ", ".join(attempt.get("codes") or []) or "ok"
    with st.expander(f"{i}. {attempt.get('stage', '?')}: {codes}", expanded=bool(attempt.get("codes"))):
        if attempt.get("sql"):
            st.code(attempt["sql"], language="sql")
        if attempt.get("error"):
            st.error(attempt["error"])

if trace.get("executed_sql"):
    with st.expander("Executed SQL"):
        st.code(trace["executed_sql"], language="sql")

st.markdown("**Policy decisions**")
decisions = trace.get("policy_decisions") or []
if decisions:
    st.dataframe(decisions, hide_index=True, width="stretch")
else:
    st.caption("No policy rule fired.")
