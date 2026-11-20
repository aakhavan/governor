"""V2 acceptance: ask-graph tracing (docs/capstone/batch4.md sections 34-35)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import env_clean  # noqa: E402

env_clean()
from _common import ROOT, check, finish, guarded, py_json, pytest_check  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth unchanged", ok, detail)
    for rel in ("src/governor/ask/graph.py", "src/governor/ask/checkpoints.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        check(f"{rel} does not import build/integrations", "governor.build" not in src and "governor.integrations" not in src, "bad import")
    check("ask graph wraps nodes", "traced(" in (ROOT / "src/governor/ask/graph.py").read_text(encoding="utf-8"), "no traced(")


def topology():
    data, err = py_json("import json; from governor.core.runtrace.registry import topology; t = topology('ask'); "
                        "print(json.dumps({'nodes': [n['id'] for n in t['nodes']], "
                        "'unlabelled': [e for e in t['edges'] if e.get('conditional') and not e.get('label')]}))")
    if data is None:
        check("topology('ask')", False, err)
        return
    need = {"guard", "retrieve_context", "plan", "clarify", "draft_sql", "validate", "dry_run", "execute", "repair",
            "answer", "record_trace"}
    miss = sorted(need - set(data["nodes"]))
    check("topology has every ask node", not miss, f"missing: {miss}" if miss else "11 nodes")
    check("every conditional edge labelled", not data["unlabelled"], str(data["unlabelled"])[:200])


guarded("static", static)
guarded("topology", topology)
pytest_check("tests/ask", ["test_ask_registry_matches_graph", "test_ask_conditional_edges_labelled",
                           "test_ask_run_log_answered_after_repair", "test_ask_run_log_guard_blocked",
                           "test_ask_clarify_is_pause", "test_ask_run_log_has_no_text_or_values"])
pytest_check("tests")
pytest_check("tests/build")
finish("V2")
