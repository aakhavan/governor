"""G8 acceptance: Streamlit thin client over the API: pages exist, no DB/SQL/policy/ask imports, AppTest suite."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, golden_leaks, grep, guarded, py_json, pytest_check  # noqa: E402

PAGES = ["apps/streamlit/client.py", "apps/streamlit/app.py", "apps/streamlit/pages/1_Ask.py", "apps/streamlit/pages/2_Trace_explorer.py",
         "apps/streamlit/pages/3_Developer.py"]
TESTS = ["test_ask_page_answers_with_fake_llm", "test_ask_page_clarify_flow", "test_trace_explorer_lists_rows",
         "test_developer_page_renders", "test_no_token_shows_login_hint"]


def files():
    miss = [p for p in PAGES if not (ROOT / p).is_file()]
    check("app and the three pages exist", not miss, f"missing: {miss}")
    hits = grep(["apps/streamlit"], r"import duckdb|duckdb\.connect|sqlglot|governor\.ask|governor\.core|governor\.eval")
    check("UI has no DB, SQL, policy or governor.ask imports", not hits, ", ".join(hits[:5]))
    api = [h for h in grep(["apps/streamlit"], r"governor\.api") if not h.startswith("apps/streamlit/client.py") and not h.startswith("apps\\streamlit\\client.py")]
    check("only client.py touches governor.api (asgi mode)", not api, ", ".join(api[:5]))
    picker = grep(["apps/streamlit"], r"selectbox\(.*role|radio\(.*role")
    check("no role picker in the UI (role comes from the token)", not picker, ", ".join(picker[:3]))
    bad = golden_leaks([f for f in (ROOT / "apps").rglob("*.py")] + [f for f in (ROOT / "tests/ui").rglob("*.py")])
    check("no golden questions in the UI or its tests", not bad, ", ".join(bad[:5]))


def client_api():
    data, err = py_json("import json, sys; sys.path.insert(0, 'apps/streamlit'); import client\n"
                        "c = client.ApiClient\n"
                        "print(json.dumps({n: callable(getattr(c, n, None)) for n in ['ask','resume','list_traces','get_trace','health']}))")
    if check("apps/streamlit/client.py importable", data is not None, err):
        miss = [k for k, v in data.items() if not v]
        check("ApiClient exposes ask/resume/list_traces/get_trace/health", not miss, f"missing: {miss}")


def compose_ui():
    t = (ROOT / "docker-compose.yml").read_text(encoding="utf-8") if (ROOT / "docker-compose.yml").is_file() else ""
    check("compose ui service points at the api service", "GOVERNOR_API_URL" in t and "api:8000" in t, "")

guarded("files", files)
guarded("client", client_api)
guarded("compose", compose_ui)
pytest_check("tests/ui", required=TESTS)
pytest_check("tests/api")
finish("G8")
