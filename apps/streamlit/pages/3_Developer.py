"""Developer view: API URL and health, LLM model ids seen in your traces, access.yaml read-only."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import ApiError, client, show_error, token_box  # noqa: E402

ACCESS_YAML = Path(__file__).resolve().parents[3] / "knowledge" / "access.yaml"

st.title("Developer")
token = token_box()
api = client(token)

st.subheader("API")
st.markdown(f"**URL:** `{'in-process (asgi)' if api.in_process else api.base_url}`")
try:
    st.json(api.health())
except ApiError as exc:
    show_error(exc)

st.subheader("Models")
st.caption("The API exposes no settings route; these are the LLM model ids recorded in your recent traces.")
if token:
    try:
        recent = api.list_traces(limit=100)
        models = sorted({m for t in recent for m in t.get("models") or []})
        st.write(models or "No traces yet.")
    except ApiError as exc:
        show_error(exc)
else:
    st.caption("Set a token to see them.")

st.subheader("access.yaml (read-only)")
st.caption("Human-owned policy. The API enforces it; this page only displays the file shipped with the UI.")
if ACCESS_YAML.is_file():
    st.code(ACCESS_YAML.read_text(encoding="utf-8"), language="yaml")
else:
    st.caption("knowledge/access.yaml is not available in this container.")
