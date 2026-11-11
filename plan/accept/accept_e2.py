"""E2 acceptance: certified KPIs over a second read-only MCP server; certified.answer unchanged."""
import sys
import os
# Pin every test-bed setting to the (empty) acceptance port so live tests skip instead of running against
# whatever database the calling shell points at.
for _k, _v in {"GOVERNOR_PG_PORT": "55433", "GOVERNOR_PG_HOST": "localhost"}.items():
    os.environ[_k] = _v
for _k in ("GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN", "GOVERNOR_BUILD_DSN", "GOVERNOR_BUILD_PASSWORD", "GOVERNOR_DEPLOY_PASSWORD",
           "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "GOVERNOR_MCP_ROLE"):
    os.environ.pop(_k, None)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, py_json, pytest_check, run  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    check("governor.ask never imports build or integrations",
          not grep(["src/governor/ask"], r"^\s*(import|from)\s+governor\.(build|integrations)"), "")
    for f in ("tests/ask/test_certified.py", "src/governor/ask/mcp_server.py", "tests/mcp/test_mcp_server.py"):
        r = run(["git", "diff", "--quiet", "main", "--", f])
        check(f"{f} unchanged against main", r.returncode == 0, "the file differs from main")
    d, err = py_json("import json, inspect, governor.ask.certified as c, governor.ask.mcp_certified as m\n"
                     "print(json.dumps({'reply': callable(getattr(c, 'answer_reply', None)),\n"
                     "                  'adapter': 'adapter' in inspect.signature(m.build_server).parameters}))")
    check("mcp_certified imports without a database", d is not None, err)
    check("certified.answer_reply exists", bool(d and d.get("reply")), "")
    check("build_server takes an adapter", bool(d and d.get("adapter")), "")
    doc = (ROOT / "docs/mcp.md").read_text(encoding="utf-8")
    for word in ("governor.ask.mcp_certified", "list_certified_kpis", "describe_kpi", "query_kpi", "gap_report"):
        check(f"docs/mcp.md mentions {word}", word in doc, "")


guarded("static", static)
pytest_check("tests/mcp", required=[
    "test_lists_four_read_only_tools_without_a_role_argument", "test_list_certified_kpis_and_gaps",
    "test_describe_kpi_certified_gap_and_unknown", "test_query_kpi_runs_validated_sql_as_the_reader_role",
    "test_query_kpi_gap_is_not_available", "test_query_kpi_bad_arguments_run_no_sql",
    "test_gap_report_lists_missing_data_and_next_step", "test_no_database_is_a_clean_error",
    "test_role_must_be_a_reader_role"])
pytest_check("tests/ask", required=["test_answer_reply_matches_answer"])
finish("E2")
