"""Raw-schema profiles written by the Airflow DAG governor_profile_raw. Talks to the API only.

Opens the profile named by the ``run_id`` query param, or offers the stored list. Shows only what the
API returned; PII columns are shown exactly as the profile marks them.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from ui_common import ApiError, require_token, show_error  # noqa: E402

COLUMN_FIELDS = ["name", "inferred_type", "null_rate", "distinct", "pii", "min", "max"]

st.title("Profiles")
api = require_token()
if api is None:
    st.stop()

wanted = st.query_params.get("run_id")
try:
    run_ids = api.list_profiles()
except ApiError as exc:
    show_error(exc)
    st.stop()

if not wanted:
    if not run_ids:
        st.info("No profiles yet. Trigger the governor_profile_raw DAG in Airflow first.")
        st.stop()
    wanted = st.selectbox("Run", run_ids)
    st.caption(f"{len(run_ids)} profile(s), newest first")

try:
    profile = api.get_profile(wanted)
except ApiError as exc:
    show_error(exc)
    st.stop()

tables = profile.get("tables") or []
relationships = profile.get("relationships") or []
st.subheader(f"Run {wanted}")
cols = st.columns(4)
cols[0].metric("Schema", profile.get("schema") or "?")
cols[1].metric("Tables", len(tables))
cols[2].metric("Rows", sum(int(t.get("rows") or 0) for t in tables))
cols[3].metric("Relationships", len(relationships))

st.markdown("**Tables**")
st.dataframe(
    [{"table": t.get("name"), "rows": t.get("rows"), "columns": len(t.get("columns") or []),
      "pii columns": sum(1 for c in t.get("columns") or [] if c.get("pii")),
      "candidate keys": "; ".join(", ".join(k) for k in t.get("candidate_keys") or [])} for t in tables],
    hide_index=True, width="stretch",
)

st.markdown("**Relationships**")
if relationships:
    st.dataframe([{"from": r.get("from"), "to": r.get("to"), "coverage": r.get("coverage")} for r in relationships],
                 hide_index=True, width="stretch")
else:
    st.caption("No relationships found.")

for t in tables:
    with st.expander(f"{t.get('name')} ({t.get('rows')} rows)"):
        st.dataframe([{f: c.get(f) for f in COLUMN_FIELDS} for c in t.get("columns") or []],
                     hide_index=True, width="stretch")
