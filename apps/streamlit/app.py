"""governor-ask UI: landing page. Run with ``streamlit run apps/streamlit/app.py``.

A thin client: every page talks to the governor API over HTTP (``client.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from ui_common import ApiError, LOGIN_HINT, client, token_box  # noqa: E402

st.set_page_config(page_title="governor-ask", page_icon=":material/policy:")
st.title("governor-ask")
st.markdown(
    "Ask questions about the billing warehouse in plain language. The API plans a query, "
    "checks it against the access policy for your role, runs it read-only and answers with "
    "the result, the SQL and where the data came from."
)

token = token_box()

st.subheader("API")
try:
    health = client().health()
    cols = st.columns(3)
    cols[0].metric("Status", health.get("status", "?"))
    cols[1].metric("Data as of", (health.get("as_of") or "not built")[:19])
    cols[2].metric("Version", health.get("version", "?"))
except ApiError as exc:
    st.error(f"API not reachable: {exc.error}")

if token:
    st.success("Token set. Use **Ask** to ask a question or **Trace explorer** to review past ones.")
else:
    st.info(LOGIN_HINT)
