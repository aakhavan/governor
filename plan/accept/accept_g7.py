"""G7 acceptance: Streamlit pages exist, AppTest suite passes, pages hold no SQL/policy logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, golden_leaks, grep, guarded, py_json, pytest_check  # noqa: E402

PAGES = ["apps/streamlit/app.py", "apps/streamlit/pages/1_Ask.py", "apps/streamlit/pages/2_Trace_explorer.py",
         "apps/streamlit/pages/3_Developer.py"]
TESTS = ["test_ask_page_answers_with_fake_llm", "test_ask_page_clarify_flow", "test_trace_explorer_lists_rows",
         "test_developer_page_renders"]


def files():
    miss = [p for p in PAGES if not (ROOT / p).is_file()]
    check("app and the three pages exist", not miss, f"missing: {miss}")
    hits = grep(["apps/streamlit"], r"import duckdb|duckdb\.connect|sqlglot|governor\.ask\.(validator|executor|graph|policy)\b|from governor\.ask import (validator|executor|graph|policy)")
    check("pages call governor.ask.service only (no DB, SQL or policy logic)", not hits, ", ".join(hits[:5]))
    bad = golden_leaks([f for f in (ROOT / "apps").rglob("*.py")] + [f for f in (ROOT / "tests/ui").rglob("*.py")])
    check("no golden questions in the UI or its tests", not bad, ", ".join(bad[:5]))


def service_api():
    data, err = py_json("import json, inspect; from governor.ask import service as s\n"
                        "print(json.dumps({n: callable(getattr(s, n, None)) for n in "
                        "['ask','resume','list_traces','get_trace','settings','update_settings']}))")
    if check("governor.ask.service importable", data is not None, err):
        miss = [k for k, v in data.items() if not v]
        check("service exposes ask/resume/list_traces/get_trace/settings/update_settings", not miss, f"missing: {miss}")


guarded("files", files)
guarded("service", service_api)
pytest_check("tests/ui", required=TESTS)
pytest_check("tests/ask")
finish("G7")
