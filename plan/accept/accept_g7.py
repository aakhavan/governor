"""G7 acceptance: API routes, token-derived roles, no role in the body, deploy files, no secrets committed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, py_json, pytest_check  # noqa: E402

ROUTES = {("GET", "/health"), ("POST", "/v1/ask"), ("POST", "/v1/threads/{thread_id}/resume"),
          ("GET", "/v1/traces"), ("GET", "/v1/traces/{trace_id}")}
TESTS = ["test_health_needs_no_token", "test_ask_requires_token", "test_role_comes_from_token",
         "test_role_in_body_rejected", "test_ask_and_resume_clarify", "test_traces_scoped_to_role",
         "test_errors_have_no_traceback"]

PROBE = r'''
import json, os
os.environ["GOVERNOR_LLM"] = "fake"
os.environ["GOVERNOR_API_TOKENS"] = "analyst:tok-analyst-accept,finance_admin:tok-admin-accept"
os.environ.setdefault("GOVERNOR_STATE_DIR", "artifacts/accept_g7_state")
from fastapi.testclient import TestClient
from governor.api.app import app
c = TestClient(app)
spec = app.openapi()
routes = sorted([m.upper(), p] for p, ops in spec["paths"].items() for m in ops)
out = {"routes": routes}
out["health"] = c.get("/health").status_code
out["no_token"] = c.post("/v1/ask", json={"question": "how many accounts are there"}).status_code
out["bad_token"] = c.post("/v1/ask", json={"question": "x"}, headers={"Authorization": "Bearer nope"}).status_code
out["role_in_body"] = c.post("/v1/ask", json={"question": "x", "role": "finance_admin"},
                             headers={"Authorization": "Bearer tok-analyst-accept"}).status_code
r = c.post("/v1/ask", json={"question": "how many accounts are there"}, headers={"Authorization": "Bearer tok-analyst-accept"})
out["ask"] = r.status_code
out["ask_keys"] = sorted(r.json()) if r.headers.get("content-type", "").startswith("application/json") else []
r = c.get("/v1/traces/does-not-exist", headers={"Authorization": "Bearer tok-analyst-accept"})
out["missing_trace"] = r.status_code
out["missing_trace_body"] = r.text[:300]
print(json.dumps(out))
'''


def api():
    data, err = py_json(PROBE, timeout=300)
    if not check("API app imports and answers with the fake LLM", data is not None, err):
        return
    got = {tuple(r) for r in data["routes"]}
    check("exactly the specified routes", got == ROUTES, f"got {sorted(got)}")
    check("/health needs no token", data["health"] == 200, data["health"])
    check("missing and unknown tokens are 401", data["no_token"] == 401 and data["bad_token"] == 401,
          f"{data['no_token']}/{data['bad_token']}")
    check("a role field in the body is rejected (422)", data["role_in_body"] == 422, data["role_in_body"])
    need = {"status", "answer", "sql", "trace_id", "thread_id"}
    check("/v1/ask works with a valid token and returns an AskResult", data["ask"] == 200 and need <= set(data["ask_keys"]),
          f"{data['ask']} {data['ask_keys']}")
    body = data["missing_trace_body"]
    check("errors are JSON without a traceback", data["missing_trace"] in (403, 404) and "Traceback" not in body
          and '"code"' in body, body[:120])


def deploy_files():
    df = ROOT / "Dockerfile"
    text = df.read_text(encoding="utf-8") if df.is_file() else ""
    check("Dockerfile builds the green warehouse and catalog at build time and runs uvicorn as non-root",
          all(k in text for k in ("build_green", "governor.core.harvest", "governor.ask.catalog", "uvicorn", "USER")), "")
    dc = ROOT / "docker-compose.yml"
    t = dc.read_text(encoding="utf-8") if dc.is_file() else ""
    check("docker-compose.yml has api and ui services and a /data volume", "api:" in t and "ui:" in t and "/data" in t, "")
    ex = ROOT / ".env.example"
    check(".env.example exists with placeholders only", ex.is_file() and "GOVERNOR_API_TOKENS" in ex.read_text(encoding="utf-8")
          and "tok-" not in ex.read_text(encoding="utf-8"), "")
    check("docs/deploy.md exists", (ROOT / "docs/deploy.md").is_file(), "")
    hits = grep(["src", "apps", "Dockerfile", "docker-compose.yml", "docs"], r"(analyst|finance_admin):[A-Za-z0-9_\-]{12,}")
    hits = [h for h in hits if not h.startswith("tests")]
    check("no real tokens in code, compose or docs", not hits, ", ".join(hits[:4]))
    log = grep(["src/governor/api"], r"log.*(token|authorization)|print\(.*token")
    check("tokens are never logged", not log, ", ".join(log[:4]))


guarded("api", api)
guarded("deploy files", deploy_files)
pytest_check("tests/api", required=TESTS)
pytest_check("tests/ask")
finish("G7")
